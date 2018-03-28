from openprocurement.ocds.export.models import (
    Award,
    Contract,
    Tender,
    release_tender,
    release_tenders,
    package_tenders,
    record_tenders,
    modelsMap,
    callbacks
)
from openprocurement.ocds.export.ext.models import (
    TenderExt,
    AwardExt,
    ContractExt,
    update_models_map,
    update_callbacks,
    release_tender_ext,
    release_tenders_ext,
    record_tenders_ext,
    package_tenders_ext
)
from openprocurement.ocds.export.ocds1_1.models import (
    TenderCan1_1,
    PeriodCan1_1,
    OrganizationCan1_1,
    ReleaseCan1_1,
    update_models_map_can1_1,
    update_callbacks_can1_1
)
from .utils import (
    award,
    contract,
    tender,
    period,
    organization,
    config
)


class TestModels(object):

    def test_award_model(self):
        new = Award(award, modelsMap, callbacks).__export__()
        assert 'lotID' not in new
        assert 'bidID' not in new

    def test_contract_model(self):
        new = Contract(contract, modelsMap, callbacks).__export__()
        assert 'suppliers' not in new
        assert 'contractID' not in new
        assert 'contractNumber' not in new

    def test_tender_model(self):
        new = Tender(tender, modelsMap, callbacks).__export__()
        assert 'bids' not in new
        assert 'lots' not in new
        assert 'tenderID' not in new


class TestModelsExt(object):

    def test_award_model(self):
        new = AwardExt(award, update_models_map(), update_callbacks()).__export__()
        assert 'lotID' in new

    def test_tender_model(self):

        new = TenderExt(tender, update_models_map(), update_callbacks()).__export__()
        assert 'lots' in new
        assert 'tenderID' in new

    def test_contract_model(self):
        new = ContractExt(contract, update_models_map(), update_callbacks()).__export__()
        assert 'contractNumber' in new
        assert 'contractID' in new


class TestModelsOcds1_1(object):
    def test_tender_model(self):
        new = TenderCan1_1(tender, update_models_map_can1_1(), update_callbacks_can1_1()).__export__()
        assert 'contractPeriod' in new
        assert 'minValue' in new

    def test_period_model(self):
        new = PeriodCan1_1(period, update_models_map_can1_1(), update_callbacks_can1_1()).__export__()
        assert 'durationInDays' in new

    def test_organization_model(self):
        new = OrganizationCan1_1(organization, update_models_map_can1_1(), update_callbacks_can1_1()).__export__()
        assert 'roles' in new

    def test_release_model(self):
        new = ReleaseCan1_1(tender, update_models_map_can1_1(), update_callbacks_can1_1()).__export__()
        assert 'parties' in new
        assert 'bids' in new


class TestExport(object):

    def test_release_tender(self):
        ten = tender.copy()
        ten['awards'] = [award.copy()]
        ten['contracts'] = [contract.copy()]
        release = release_tender(ten, modelsMap, callbacks, 'test')
        assert 'ocid' in release
        assert release['ocid'] == 'test-{}'.format(ten['tenderID'])
        assert release['date'] == ten['dateModified']
        assert release['tag'] == ['tender', 'award', 'contract']
        assert 'bids' not in release
        assert 'bid' not in release['tag']

    def test_release_package(self):
        pack = package_tenders([tender for _ in xrange(3)], modelsMap, callbacks, config)
        assert len(pack['releases']) == 3
        for field in ['license', 'publicationPolicy']:
            assert field in pack
            assert pack[field] == 'test'
        assert 'name' in pack['publisher']
        assert pack['publisher']['name'] == 'test'

    def test_release_tenders(self):
        patch1 = [
            {"op": "add",
             "path": "/test",
             "value": "test"}
        ]
        ten = tender.copy()
        ten['patches'] = [patch1]
        releases = release_tenders(ten, modelsMap, callbacks, 'test')
        assert len(releases) == 2
        assert 'tenderUpdate' not in releases[1]
        patch2 = [
            {"op": "replace",
             "path": "/description",
             "value": "test"
             }
        ]
        ten['patches'] = [patch2]
        releases = release_tenders(ten, modelsMap, callbacks, 'test')
        assert 'tenderUpdate' in releases[1]['tag']
        assert releases[0]['tender']['description'] != 'test'
        assert releases[1]['tender']['description'] == 'test'
        ten['awards'] = [award]
        patch3 = [
            {"op": "replace",
             "path": "/awards/0/status",
             "value": "test"
             }
        ]
        ten['patches'] = [patch3]
        releases = release_tenders(ten, modelsMap, callbacks, 'test')
        assert 'awardUpdate' in releases[1]['tag']
        assert releases[0]['awards'][0]['status'] != 'test'
        assert releases[1]['awards'][0]['status'] == 'test'
        patch4 = [
            {"op": "replace",
             "path": "/contracts/0/status",
             "value": "test"
             }
        ]
        ten['contracts'] = [contract]
        ten['patches'] = [patch3, patch4]
        releases = release_tenders(ten, modelsMap, callbacks, 'test')
        assert 'awardUpdate' in releases[1]['tag']
        assert 'contractUpdate' in releases[2]['tag']
        assert releases[1]['awards'][0]['status'] == 'test'
        assert releases[2]['contracts'][0]['status'] == 'test'
        patch5 = [{'op': 'add', 'path': '/contracts',
          'value': [{'status': 'test', 'description': 'Some test contract'
          }]}]
        ten = tender.copy()
        ten['patches'] = [patch5]
        releases = release_tenders(ten, modelsMap, callbacks, 'test')

    def test_record(self):
        ten = tender.copy()
        patch = [
            {"op": "replace",
             "path": "/description",
             "value": "test"
             }
        ]
        ten['patches'] = [patch]
        record = record_tenders(ten, modelsMap, callbacks, 'test')
        assert len(record['releases']) == 2
        assert record['ocid'] == record['releases'][0]['ocid']


class TestExportExt(object):

    def test_models_map_update(self):
        assert "bids" in update_models_map()

    def test_callbacks_update(self):
        assert 'bids' in update_callbacks()

    def test_release_tender(self):
        release = release_tender_ext(tender, update_models_map(), update_callbacks(), 'test')
        assert 'bid' in release['tag']

    def test_release_tenders(self):
        ten = tender.copy()
        patch = [
            {"op": "replace",
             "path": "/bids/0/status",
             "value": "test"
             }
        ]
        ten['patches'] = [patch]
        releases = release_tenders_ext(ten, update_models_map(), update_callbacks(), 'test')
        assert len(releases) == 2
        assert 'bidUpdate' in releases[1]['tag']
        patch1 = [
            {"op": "replace",
             "path": "/description",
             "value": "test"
             }
        ]
        ten['patches'] = [patch1]
        releases = release_tenders_ext(ten, update_models_map(), update_callbacks(), 'test')
        assert 'tenderUpdate' in releases[1]['tag']
        patch2 = [{'op': 'add', 'path': '/bids/1',
          'value': {'status': 'test', 'description': 'Some test bid',
          }}]
        ten = tender.copy()
        ten['patches'] = [patch2]
        releases = release_tenders_ext(ten, update_models_map(), update_callbacks(), 'test')
        assert 'bid' in releases[1]['tag']

    def test_release_package(self):
        pack = package_tenders_ext([tender for _ in xrange(3)], update_models_map(), update_callbacks(), config)
        assert len(pack['releases']) == 3
        for field in ['license', 'publicationPolicy']:
            assert field in pack
            assert pack[field] == 'test'
        assert 'name' in pack['publisher']
        assert pack['publisher']['name'] == 'test'

    def test_record(self):
        ten = tender.copy()
        patch = [
            {"op": "replace",
             "path": "/description",
             "value": "test"
             }
        ]
        ten['patches'] = [patch]
        record = record_tenders_ext(ten, update_models_map(), update_callbacks(), 'test')
        assert len(record['releases']) == 2
        assert record['ocid'] == record['releases'][0]['ocid']
