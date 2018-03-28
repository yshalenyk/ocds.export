# -*- coding: utf-8 -*-
import ocdsmerge
import yaml
import os
import zipfile
import argparse
from simplejson import dump
from gevent.pool import Pool
from iso8601 import parse_date
from uuid import uuid4
from datetime import datetime
from collections import Counter
from functools import reduce
from .exceptions import LBMismatchError

from boto.s3 import connect_to_region
from boto.s3.connection import (
    OrdinaryCallingFormat,
    S3ResponseError
)

from logging import getLogger, ERROR
from logging.config import dictConfig


logger = getLogger(__name__)
getLogger('boto').setLevel(ERROR)


with open(os.path.join(os.path.dirname(__file__),
                       'unit_codes.yaml'), 'r') as stream:
    units = yaml.load(stream)


def get_torrent_link(bucket, path):
    return 'https://s3-eu-west-1.amazonaws.com/'\
            '{}/{}releases.zip?torrent'.format(bucket, path)


def convert_status(tender):
    return tender.get('status').split('.')[0] if tender.get('status') else None


def file_size(path, name):
    return (os.stat(os.path.join(path, name)).st_size) / 1000000


def make_zip(name, base_dir, skip=None):
    if not skip:
        skip = []

    skip.append(name)
    with zipfile.ZipFile(os.path.join(base_dir, name),
                         'w', zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        for f in [f for f in os.listdir(base_dir) if f not in skip]:
            zf.write(os.path.join(base_dir, f))



def parse_dates(dates):
    return (parse_date(dates[0]).isoformat(),
            parse_date(dates[1]).isoformat())


def connect_bucket(config):
    try:
        conn = connect_to_region(
                    'eu-west-1',
                    aws_access_key_id=config.get('aws_access_key_id', os.environ.get('AWS_ACCESS_KEY_ID', '')),
                    aws_secret_access_key=config.get('aws_secret_access_key', os.environ.get('AWS_SECRET_ACCESS_KEY', '')),
                    calling_format=OrdinaryCallingFormat()
                    )
        return conn.get_bucket(config.get('bucket'))
    except S3ResponseError as e:
        logger.warn('Unable to connect to s3. Error: {}'.format(e))
        return False


def read_config(path):
    with open(path) as cfg:
        config = yaml.load(cfg)
    dictConfig(config.get('logging', ''))
    return config


def now():
    return parse_date(datetime.now().isoformat()).isoformat()


def get_ocid(prefix, tenderID):
    """greates unique contracting identifier"""
    return "{}-{}".format(prefix, tenderID)


def build_package(config):
    package = {}
    package['publishedDate'] = now()
    for k in ['publisher', 'license', 'publicationPolicy']:
        if k in config:
            package[k] = config.get(k)
    return package


def unique_tenderers(tender):
    """leave only unique tenderers as required by standard"""
    bids = tender.get('bids')
    if not bids:
        return
    tenderers = [tenderer for bid in bids for tenderer in bid.get('tenderers', [])]
    return {t['identifier']['id']: t for t in tenderers}.values() if tenderers else []


def unique_documents(documents, extension=False):
    """adds `-<number>` to docs with same ids"""
    if not documents:
        return
    if extension:
        for doc in documents:
            if 'documentOf' in doc:
                doc['documentScope'] = doc.pop('documentOf')
    cout = Counter(doc['id'] for doc in documents)
    for i in [i for i, c in cout.iteritems() if c > 1]:
        for index, d in enumerate([d for d in documents if d['id'] == i]):
            d['id'] = d['id'] + '-{}'.format(index)
    return documents


def convert_cancellation_and_tenderers(tender):
    cancellations = tender.get('cancellations', '')
    if cancellations:
        for cancellation in cancellations:
            if cancellation['cancellationOf'] == 'tender':
                tender['pendingCancellation'] = True
            elif cancellation['cancellationOf'] == 'lot':
                for lot in tender.get('lots', []):
                    if lot['id'] == cancellation['relatedLot']:
                        lot['pendingCancellation'] = True
            cancellation_docs = prepare_cancellation_documents(cancellation)
            if 'documents' in tender:
                tender['documents'].extend(cancellation_docs)
            else:
                tender['documents'] = cancellation_docs
    if unique_tenderers(tender):
        tender['tenderers'] = unique_tenderers(tender)
    return tender


def prepare_cancellation_documents(cancellation):
    for doc in cancellation.get('documents', []):
        doc['documentType'] = 'tenderCancellation' if \
                cancellation['cancellationOf'] == 'tender' else 'lotCancellation'
    return cancellation.get('documents', [])


def convert_questions(tender):
    questions = tender.get('questions')
    if not questions:
        return
    for question in questions:
        if question['questionOf'] == 'lot':
            question['relatedLot'] = question['relatedItem']
            del question['relatedItem']
    return questions


def award_converter(tender):
    if 'lots' in tender:
        for award in tender.get('awards', []):
            award['items'] = [
                item for item in tender.get('items')
                if item.get('relatedLot') == award.get('lotID')
            ]
    else:
        for award in tender.get('awards', []):
            award['items'] = tender.get('items')
    return tender.get('awards', [])


def convert_bids(bids):
    if not bids:
        return
    new = []
    for _bid in bids:
        if 'lotValues' in _bid:
            for lotval in _bid['lotValues']:
                bid = _bid.copy()
                bid['relatedLot'] = lotval['relatedLot']
                bid['value'] = lotval.get('value')
                new.append(bid)
        else:
            new.append(_bid)
    return {"details": new}


def convert_unit_and_location(items):
    if not items:
        return
    new = []
    for item in items:
        new_loc = {}
        if 'unit' in item:
            unit_code = item['unit'].get('code')
            if units.get(unit_code):
                item['unit'] = units[unit_code]
                item['unit']['scheme'] = "UNCEFACT"
                item['unit']['id'] = unit_code
            elif item['unit'].get('id'):
                pass
            else:
                item['unit']['id'] = unit_code
        if 'deliveryLocation' in item:
            if item['deliveryLocation'].get('latitude'):
                new_loc = {'geometry': {'coordinates': item['deliveryLocation'].values()}}
                item['deliveryLocation'] = new_loc
            elif 'geometry' in item['deliveryLocation']:
                pass
            else:
                del item['deliveryLocation']
        new.append(item)
    return new


def create_auction(tender):
    auctions = []
    auction = {}
    lots = tender.get('lots', [])
    for lot in lots:
        auction['url'] = lot.get('auctionUrl')
        auction['minimalStep'] = lot.get('minimalStep')
        auction['period'] = lot.get('auctionPeriod')
        auction['relatedLot'] = lot.get('id')
        auctions.append(auction)
        auction = {}
    else:
        auction['url'] = tender.get('auctionUrl')
        auction['minimalStep'] = tender.get('minimalStep')
        auction['period'] = tender.get('auctionPeriod')
    if any(auction.values()):
        auctions.append(auction)
        return auctions
    return auctions


def mode_test(tender):
    """ drops all test mode tenders """
    return 'ТЕСТУВАННЯ'.decode('utf-8') in tender['title']


def get_start_point(forward, backward, cookie, queue,
                    callback=lambda x: x, extra={}):
    forward_params = {'feed': 'changes'}
    backward_params = {'feed': 'changes', 'descending': '1'}
    if extra:
        [x.update(extra) for x in [forward_params, backward_params]]
    r = backward.get_tenders(backward_params)
    if backward.session.cookies != cookie:
        raise LBMismatchError
    backward_params['offset'] = r['next_page']['offset']
    forward_params['offset'] = r['prev_page']['offset']
    queue.put(filter(callback, r['data']))
    return forward_params, backward_params


def exists_or_modified(storage, doc):
    resp = storage.view('tenders/by_dateModified', key=doc['id'])
    try:
        date_mod = next(r['value'] for r in resp)
        return date_mod < doc.get('dateModified')
    except StopIteration:
        return True


def compile_releases(releases, versioned=False):
    return ocdsmerge.merge(releases) if not versioned\
            else ocdsmerge.merge_versioned(releases)


def dump_json(path, name, data, pretty=False):
    with open(os.path.join(path, name), 'w') \
            as stream:
        if pretty:
            dump(data, stream, indent=4)
        else:
            dump(data, stream)


def links(path, skip=['example.json', 'index.html', 'releases.zip', 'records.zip']):
    for _file in sorted([f for f in os.listdir(path) if
                        f not in skip]):
        yield {
            'size': file_size(path, _file),
            'link': _file
        }


def create_html(environment, config, date, path):
    template = environment.get_template('index.html')
    key = 'merged_{}' if 'ext' not in path else 'merged_with_extensions_{}'
    torrent_link = get_torrent_link(config.get('bucket'), key.format(date))
    zip_size = file_size(path, 'releases.zip')
    with open(os.path.join(path, 'index.html'), 'w') as stream:
        stream.write(template.render(dict(zip_size=zip_size,
                                          torrent_link=torrent_link,
                                          links=links(path))))

def update_index(templates, bucket):
    template = templates.get_template('base.html')
    index = templates.get_template('index.html')
    dirs = [d.name for d in bucket.list('merged', '/') if 'full' not in d.name
            and '2017-07-26' not in d.name and d.name != 'merged_2018-02-16']
    html = template.render(dict(links=[x.strip('/') for x in dirs]))
    k = bucket.get_key('index.html')
    k.set_contents_from_string(html)
    k = k.copy(k.bucket.name, k.name, {'Content-Type':'text/html'})
    logger.info('Updated base index')
    def update_secondary_index(path):
        ctx = [p.name for p in bucket.list(path, '/')
               if not p.name.endswith('html')]
        if 'record' in p.name:
            archive = bucket.get_key(path + 'records.zip')
        else:
            archive = bucket.get_key(path + 'releases.zip')
        size = None
        if archive:
            size = archive.size / 1024 / 1024
        torrent_link = get_torrent_link(bucket.name, path)
        files = sorted([{
            'link': f.split('/')[1],
            'size': bucket.get_key(f).size / 1024 / 1024
        } for f in ctx], key=lambda x: x.get('link'))
        result = index.render(dict(zip_size=size,
                                   torrent_link=torrent_link,
                                   links=files))
        key = bucket.get_key(os.path.join(path, 'index.html'))
        if not key:
            key = bucket.new_key(os.path.join(path, 'index.html'))
        key.set_contents_from_string(result)
        key = key.copy(key.bucket.name, key.name, {'Content-Type':'text/html'})
        logger.info('Updated index in {}'.format(path))

    pool = Pool(10)
    pool.map(update_secondary_index, dirs)

        
def parse_args():
    parser = argparse.ArgumentParser('Release Packages')
    parser.add_argument('-c', '--config',
                        required=True,
                        help="Path to configuration file")
    parser.add_argument('-d', action='append',
                        dest='dates',
                        default=[],
                        help='Start-end dates to generate package')
    parser.add_argument('-n', '--number')
    parser.add_argument('-r', '--records',
                        action='store_true',
                        default=False,
                        help='Generate record too')
    parser.add_argument('-rec',
                        action='store_true',
                        help='Choose to start dump record packages',
                        default=False)
    parser.add_argument('-contracting',
                        action='store_true',
                        help='Choose to include contracting',
                        default=False)
    return parser.parse_args()


def connect_bucket(config):
    try:
        conn = connect_to_region(
                    'eu-west-1',
                    aws_access_key_id=config.get('aws_access_key_id', os.environ.get('AWS_ACCESS_KEY_ID', '')),
                    aws_secret_access_key=config.get('aws_secret_access_key', os.environ.get('AWS_SECRET_ACCESS_KEY', '')),
                    calling_format=OrdinaryCallingFormat()
                    )
        return conn.get_bucket(config.get('bucket'))
    except S3ResponseError as e:
        logger.warn('Unable to connect to s3. Error: {}'.format(e))
        return False


def parties(raw_data):
    """ Gets all organization info from tenderers, suppliers, procuringEntities and buyers """
    tenderers = raw_data.get('tenderers')
    if tenderers:
        for tenderer in tenderers:
            tenderer['roles'] = ['tenderer']
    else:
        tenderers = []
    procuringEntity = raw_data.get('procuringEntity')
    procuringEntity['roles'] = ['buyer', 'procuringEntity']
    suppliers = []
    awards = raw_data.get('awards')
    if awards:
        new_suppliers = []
        for award in awards:
            award_suppliers = award.get('suppliers')
            if award_suppliers:
                new_suppliers += award_suppliers
        for supplier in new_suppliers:
            supplier['roles'] = ['supplier']
        suppliers += new_suppliers
    contracts = raw_data.get('contracts')
    if contracts:
        new_suppliers = []
        for contract in contracts:
            contract_suppliers = contract.get('suppliers')
            if contract_suppliers:
                new_suppliers += contract_suppliers
        for supplier in new_suppliers:
            supplier['roles'] = ['supplier']
        suppliers += new_suppliers
    bids = raw_data.get('bids')
    if bids:
        new_tenderers = []
        for bid in bids:
            bid_tenderers = bid.get('tenderers')
            if bid_tenderers:
                new_tenderers += bid_tenderers
        for tenderer in new_tenderers:
            tenderer['roles'] = ['tenderer']
        tenderers += new_tenderers
    ids = {}

    def identify(item):
        id = "{}-{}".format(item['identifier']['scheme'], item['identifier']['id'])
        if id not in ids:
            ids[id] = item
        else:
            for role in item['roles']:
                if role not in ids[id]:
                    ids[id]['roles'].append(role)

    for tenderer in tenderers:
        identify(tenderer)
    for supplier in suppliers:
        identify(supplier)
    identify(procuringEntity)
    return ids.values()


def contractPeriod(raw_data):
    """ Gets contract.period for one lot procedures """
    contracts = raw_data.get('contracts')
    if contracts and len(contracts) == 1:
        return contracts[0].get('period')


def minValue(raw_data):
    """ Gets tender.value for active tenders, and contract.value for one lot procedures"""
    if 'active' in raw_data.get('status'):
        return raw_data.get('value')
    else:
        contracts = raw_data.get('contracts')
        if contracts and len(contracts) == 1:
            return contracts[0].get('value')


def statistics(details):
    """ Creates bids.statistics from tender.bids """
    measures = {}
    if details:
        for detail in details:
            status = detail['status']
            if status in measures:
                measures[status] += 1
            else:
                measures[status] = 1
        return [{'measure': measure, 'number': value, 'id': uuid4().hex} for measure, value in measures.iteritems()]


def bids(raw_data):
    """ Gets tender.bids """
    details = raw_data.get('bids')
    if details:
        return {
            'details': details,
            'statistics': statistics(details)
        }
