# -*- coding: utf-8 -*-
import argparse
import yaml
import iso8601
import os
import time
import logging
import tarfile
import math
from logging.config import dictConfig
from simplejson import dump
from openprocurement.ocds.export.helpers import mode_test
from openprocurement.ocds.export.storage import TendersStorage
from openprocurement.ocds.export.models import package_tenders
from uuid import uuid4
# from boto import S3Connection
# from filechunkio import FileChunkIO

URI = 'https://fake-url/tenders-{}'.format(uuid4().hex)
Logger = logging.getLogger(__name__)


def read_config(path):
    with open(path) as cfg:
        config = yaml.load(cfg)
    dictConfig(config.get('logging', ''))
    return config


def parse_args():
    parser = argparse.ArgumentParser('Release Packages')
    parser.add_argument('-c', '--config', required=True, help="Path to configuration file")
    parser.add_argument('-d', action='append', dest='dates', default=[], help='Start-end dates to generate package')
    parser.add_argument('-n', '--number')
    return parser.parse_args()


def parse_dates(dates):
    return iso8601.parse_date(dates[0]).isoformat(), iso8601.parse_date(dates[1]).isoformat()


def dump_package(tenders, config):
    info = config['release']
    try:
        package = package_tenders(tenders, config.get('release'))
    except Exception as e:
        Logger.info('Error: {}'.format(e))
        return
    path = os.path.join(config['path'], 'release-{}.json'.format(time.time()))
    with open(path, 'w') as outfile:
        dump(package, outfile)


def put_to_s3(path):
    conn = S3Connection(os.environ['AWS_ACCESS_KEY'], os.environ['AWS_SECRET_KEY'])
    b = conn.get_bucket('ocds.prozorro.openprocurement.io')
    for file in os.listdir(path):
        source_file = os.path.join(path, file)
        source_size = os.stat(source_file).st_size
        mp = b.initiate_multipart_upload(os.path.basename(file))
        chunk_size = 52428800
        chunk_count = int(math.ceil(source_size / float(chunk_size)))
        for i in range(chunk_count):
            offset = chunk_size * i
            bytes = min(chunk_size, source_size - offset)
            with FileChunkIO(source_file, 'r', offset=offset, bytes=bytes) as fp:
                mp.upload_part_from_file(fp, part_num=i + 1)
        mp.complete_upload()


def run():
    args = parse_args()
    releases = []
    config = read_config(args.config)
    _tenders = TendersStorage(config['tenders_db']['url'], config['tenders_db']['name'])
    info = config.get('release')
    Logger.info('Start packaging')
    if not os.path.exists(config.get('path')):
        os.makedirs(config.get('path'))

    if args.dates:
        datestart, datefinish  = parse_dates(args.dates)
        tenders = [t['value'] for t in _tenders.db.view('tenders/byDateModified', startkey=datestart, endkey=datefinish)]
        dump_package(tenders, config)
    else:
        count = 0
        total = int(args.number) if args.number else 10000
        tenders = []
        for tender in _tenders:
            tenders.append(tender)
            count += 1
            if count == total:
                Logger.info('dumping {} packages'.format(len(tenders)))
                dump_package(tenders, config)
                count = 0
                tenders = []
        if tenders:
            Logger.info('dumping {} packages'.format(len(tenders)))
            dump_package(tenders, config)
        put_to_s3(config.get('path'))
