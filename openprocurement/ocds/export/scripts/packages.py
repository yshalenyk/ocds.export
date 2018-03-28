# -*- coding: utf-8 -*-
import os
import logging
import couchdb.json
import zipfile
import boto3
import requests
from simplejson import dump, dumps
from gevent import spawn, sleep, joinall
from os.path import join
from gevent.queue import Queue
from gevent.event import Event
from jinja2 import Environment, PackageLoader
from openprocurement.ocds.export.storage import TendersStorage
from openprocurement.ocds.export.models import package_tenders, package_records,\
    callbacks, modelsMap
from openprocurement.ocds.export.ext.models import (
    package_tenders_ext,
    package_records_ext,
    update_callbacks,
    update_models_map
)
from openprocurement.ocds.export.ocds1_1.models import (
    update_callbacks_can1_1,
    update_models_map_can1_1,
    package_tenders_can1_1,
    package_records_can1_1
)
from openprocurement.ocds.export.helpers import (
    read_config,
    parse_dates,
    update_index,
    parse_args,
    connect_bucket
)
logging.getLogger('boto').setLevel(logging.WARN)
logging.getLogger('boto3').setLevel(logging.WARN)
logging.getLogger('botocore').setLevel(logging.WARN)
couchdb.json.use('simplejson')


ENV = Environment(
    loader=PackageLoader('openprocurement.ocds.export', 'templates'),
    trim_blocks=True
)
LOGGER = logging.getLogger(__name__)
REGISTRY = {
    "max_date": None,
    "bucket": None,
    "contracting": False,
    'tenders_storage': None,
    "record": False,
    "config": {},
    "db": None,
    "contracts_storage": None,
    'can_url': 'http://{}/merged_{}/{}',
    'ext_url': 'http://{}/merged_with_extensions_{}/{}',
    'can1_1_url': 'http://{}/merged_with_ocds1.1_{}/{}',
    'zip_path': '',
    'zipq': Queue(),
    'zipq_ext': Queue(),
    'zipq_new': Queue(),
    'done': Event(),
    'archives': Queue(),
}
REGISTRY['package_funcs'] = [package_records, package_records_ext, package_records_can1_1] if REGISTRY['record']\
                            else [package_tenders, package_tenders_ext, package_tenders_can1_1]


def dump_json_to_s3(name, data, pretty=False):
    LOGGER.info('Upload {} to s3 bucket'.format(name))
    time = REGISTRY['max_date']

    dir_name = 'merged_with_extensions_{}/{}'.format(time, name) if\
               'extensions' in data['uri'] else 'merged_{}/{}'.format(time, name)
    try:
        if pretty:
            REGISTRY['bucket'].put_object(Key=dir_name, Body=dumps(data, indent=4), ContentType="application/json")
        else:
            REGISTRY['bucket'].put_object(Key=dir_name, Body=dumps(data), ContentType="application/json")
        del data
        LOGGER.info("Successfully uploaded {}".format(name))
    except Exception as e:
        LOGGER.fatal("Exception during upload {}".format(e))


def zip_package(name, data):
    if 'extension' in data['uri']:
        zip_path = REGISTRY['zip_path_ext']
    elif 'ocds1.1' in data['uri']:
        zip_path = REGISTRY['zip_path_can1_1']
    else:
        zip_path = REGISTRY['zip_path']
    full_path = join(zip_path, 'releases.zip')

    with zipfile.ZipFile(full_path, 'a', zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        if not isinstance(data, (str, unicode)):
            data = dumps(data)
        try:
            zf.writestr(name, data)
            LOGGER.info("{} written to archive {}".format(name, full_path))
            del data
        except:
            LOGGER.fatal("Unable to write package {} to archive {}".format(name, full_path))


def upload_archives():
    LOGGER.info('Start uploading archives')
    dirs = [
        'merged_{}/releases.zip'.format(REGISTRY['max_date']),
        'merged_with_extensions_{}/releases.zip'.format(REGISTRY['max_date'])
    ]

    paths = [
        join(REGISTRY['zip_path'], 'releases.zip'),
        join(REGISTRY['zip_path_ext'], 'releases.zip'),
    ]
    g = []
    for path, name in zip(paths, dirs):
        g.append(spawn(REGISTRY['bucket'].upload_file(path, name)))
    joinall(g)

def upload_releases_json(amount, max_date):
    upload_paths = ["merged_with_extensions_{}/releases.json".format(max_date), "merged_{}/releases.json".format(max_date)]
    listing_paths = ["http://{}/merged_with_extensions_{}", "http://{}/merged_{}"]
    for upload, listing in zip(upload_paths, listing_paths):
        to_upload = {
            "links": {
                "all": [listing.format(REGISTRY['bucket'].name, max_date)
                        + "/release-{0:07d}.json".format(k)
                        for k in range(1, amount + 1)]
            }
        }
        REGISTRY['bucket'].put_object(Key=upload, Body=dumps(to_upload, indent=4), ContentType="application/json")

def fetch_and_dump(total):
    num = 0
    result = []
    nth = 0
    for res in REGISTRY['tenders_storage'].get_tender(REGISTRY['contracts_storage']):
        if num == total:
            nth += 1
            start = result[0]['id']
            end = result[-1]['id']
            LOGGER.info('Start packaging {}th package! Params: startdoc={},'
                        ' enddoc={}'.format(nth, start, end))
            name = 'record-{0:07d}.json'.format(nth) if REGISTRY['record'] else 'release-{0:07d}.json'.format(nth)
            max_date = REGISTRY['max_date']
            try:
                for pack, params in zip(REGISTRY['package_funcs'],
                                        [{'uri': REGISTRY['can_url'],
                                          'models': modelsMap,
                                          'callbacks': callbacks,
                                          'q': REGISTRY['zipq']},
                                         {'uri': REGISTRY['ext_url'],
                                          'models': update_models_map(),
                                          'callbacks': update_callbacks(),
                                          'q': REGISTRY['zipq_ext']},
                                         {'uri': REGISTRY['can1_1_url'],
                                          'models': update_models_map_can1_1(),
                                          'callbacks': update_callbacks_can1_1(),
                                          'q': REGISTRY['zipq_new']}]
                                        ):
                    LOGGER.info("Start package: {}".format(pack.__name__))
                    package = pack(result, params['models'], params['callbacks'], REGISTRY['config'].get('release'))
                    package['uri'] = params['uri'].format(REGISTRY['config'].get("bucket"), max_date, name)
                    if params['uri'] == REGISTRY['can1_1_url']:
                        package['version'] = "1.1"
                    if nth == 1:
                        pretty_package = pack(result[:24], params['models'], params['callbacks'], REGISTRY['config'].get('release'))
                        pretty_package['uri'] = params['uri'].format(REGISTRY['config'].get("bucket"), max_date, 'example.json')
                        dump_json_to_s3('example.json', pretty_package, pretty=True)

                    dump_json_to_s3(name, package)
                    zip_package(name, package)
                    del package
                result = [res]
                num = 1
            except Exception as e:
                LOGGER.info('Error: {}'.format(e))
                return

            LOGGER.info('Done {}th package! Params: startdoc={}, enddoc={}'.format(nth, start, end))
        else:
            result.append(res)
            num += 1
    return nth

def run():
    args = parse_args()
    config = read_config(args.config)
    REGISTRY['config'] = config
    handler = logging.FileHandler(os.path.join(config.get('log_dir'), 'pack.log'))
    formatter = logging.Formatter('%(asctime)s  %(name)-10s %(levelname)-7s %(message)s')
    handler.setFormatter(formatter)
    LOGGER.addHandler(handler)
    REGISTRY['bucket'] = boto3.resource('s3',
                                        aws_access_key_id=config.get("aws_access_key_id"),
                                        aws_secret_access_key=config.get("aws_secret_access_key")).Bucket(config['bucket']
                                        )
    REGISTRY['tenders_storage'] = TendersStorage(config['tenders_db']['url'],
                                                 config['tenders_db']['name'])
    REGISTRY['db'] = REGISTRY['tenders_storage']
    LOGGER.info('Start packaging')
    REGISTRY['record'] = args.rec
    REGISTRY['contracting'] = args.contracting
    REGISTRY['zip_path'] = config['path_can']
    REGISTRY['zip_path_ext'] = config['path_ext']
    REGISTRY['zip_path_can1_1'] = config['path_can1_1']
    nam = 'records' if args.rec else 'releases'

    if args.dates:
        datestart, datefinish = parse_dates(args.dates)
        to_release = REGISTRY['tenders_storage'].get_between_dates(datestart, datefinish)
        if args.rec:
            package_func = package_records_ext if args.ext else package_records
        else:
            package_func = package_tenders_ext if args.ext else package_tenders
        pack = package_func(list(to_release), config)
        name = '{}_between_{}_{}'.format(nam,
                                         datestart.split('T')[0],
                                         datefinish.split('T')[0])
        with open(os.path.join(config['path'], name, 'w')) as stream:
            dump(pack, stream)
    else:
        for archive in [REGISTRY['zip_path'], REGISTRY['zip_path_ext']]:
            path = os.path.join(archive, 'releases.zip')
            if os.path.exists(path):
                os.remove(path)
        max_date = REGISTRY['tenders_storage'].get_max_date().split('T')[0]
        REGISTRY['max_date'] = max_date
        total = int(args.number) if args.number else 4096
        sleep(1)
        LOGGER.info("Start working")
        amount = fetch_and_dump(total)
        upload_archives()
        bucket = connect_bucket(config)
        upload_releases_json(amount, max_date)
        update_index(ENV, bucket)
        requests.get('http://ping.pushmon.com/pushmon/ping/WDMnYJy')
