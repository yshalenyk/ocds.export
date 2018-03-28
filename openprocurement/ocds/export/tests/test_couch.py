import pytest
import couchdb
from openprocurement.ocds.export.storage import (
    TendersStorage,
)
from .utils import tender


coudb_url = 'http://127.0.0.1:5984'
db_name = 'test'
SERVER = couchdb.Server(coudb_url)


@pytest.fixture(scope='function')
def db(request):
    def delete():
        del SERVER[db_name]

    if db_name in SERVER:
        delete()
    SERVER.create(db_name)
    request.addfinalizer(delete)


@pytest.fixture(scope='function')
def storage(request):
    storage = TendersStorage(coudb_url, db_name)
    storage.save(tender)
    return storage


class TestStorage(object):

    @pytest.mark.parametrize('storage', [TendersStorage])
    def test_create(self, storage):
        if db_name in SERVER:
            del SERVER[db_name]
        storage = storage(coudb_url, db_name)
        assert db_name in SERVER

    def test_tender_iter(self, db, storage):
        for item in storage.get_tender():
            assert item == tender

    def test_tender_date_modified(self, db, storage):
        for resp in storage.view('tenders/by_dateModified'):
            assert resp['value'] == tender['dateModified']

    def test_between_dates(self, db, storage):
        ten = tender.copy()
        ten['_id'] = 'test'
        ten['dateModified'] = "2017-07-21T20:10:40.460918+03:00"
        storage.save(ten)
        assert len(list(storage.get_between_dates("2015-07-21", "2016-07-22"))) == 1
        assert len(list(storage.get_between_dates("2015-07-21", "2018-07-22"))) == 2

    def test_max_date(self, db, storage):
        ten1 = tender.copy()
        ten2 = tender.copy()
        ten1['_id'] = 'test'
        ten2['_id'] = 'test1'
        ten1['dateModified'] = "2017-07-21T20:10:40.460918+03:00"
        ten2['dateModified'] = "2020-07-21T20:10:40.460918+03:00"
        storage.save(ten1)
        storage.save(ten2)
        assert storage.get_max_date() == max(ten2['dateModified'], ten1['dateModified'])
