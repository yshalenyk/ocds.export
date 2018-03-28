import jsonpatch
import iso8601
from copy import deepcopy


def update_models_map_can1_1():
    global modelsMap
    models_map_ext = deepcopy(modelsMap)
    models_map_ext['tender'] = (TenderCan1_1, {})
    models_map_ext['tenderPeriod'] = (PeriodCan1_1, {})
    models_map_ext['contractPeriod'] = (PeriodCan1_1, {})
    models_map_ext['enquiryPeriod'] = (PeriodCan1_1, {})
    models_map_ext['period'] = (PeriodCan1_1, {})
    models_map_ext['awardPeriod'] = (PeriodCan1_1, {})
    for key in ('tenderers', 'suppliers', 'procuringEntity', 'buyer'):
        del models_map_ext[key]
    models_map_ext['parties'] = (OrganizationCan1_1, [])
    models_map_ext['value'] = (Value, {})
    models_map_ext['bids'] = (Bids, {})
    models_map_ext['details'] = (Bid, [])
    models_map_ext['statistics'] = (BidStatistics, [])
    models_map_ext['eligibilityDocuments'] = (Document, [])
    return models_map_ext


from openprocurement.ocds.export.models import (
    modelsMap,
    callbacks,

    Award,
    Tender,
    Value,
    Model,
    Unit,
    Document,
    Release,
    Organization,
    Period,
)
from openprocurement.ocds.export.helpers import (
    contractPeriod,
    parties,
    minValue,
    bids,

    compile_releases,
    build_package,
)


def update_callbacks_can1_1():
    global callbacks
    callbacks_ext = deepcopy(callbacks)
    callbacks_ext['contractPeriod'] = contractPeriod
    callbacks_ext['parties'] = parties
    callbacks_ext['minValue'] = minValue
    callbacks_ext['bids'] = bids
    callbacks_ext['details'] = lambda raw_data: raw_data.get('details')
    callbacks_ext['statistics'] = lambda raw_data: raw_data.get('statistics')
    return callbacks_ext


class PeriodCan1_1(Period):
    __slots__ = Period.__slots__

    @property
    def durationInDays(self):
        return (
            iso8601.parse_date(self.endDate) - iso8601.parse_date(self.startDate)
        ).days


class UnitCan1_1(Unit):
    __slots__ = Unit.__slots__ + ('uri',)


class OrganizationCan1_1(Organization):
    __slots__ = Organization.__slots__ + ('roles', 'id')

    @property
    def id(self):
        return "{}-{}".format(self.identifier.scheme, self.identifier.id)


class BidStatistics(Model):
    __slots__ = (
        'id',
        'measure',
        'number',
        'date',
        'notes'
    )

    def __export__(self):
        data = Model.__export__(self)
        data['value'] = data.pop('number')
        return data


class Bid(Model):

    __slots__ = (
        'id',
        'date',
        'status',
        'value',
        'documents',
        'relatedLot',
        'participationUrl',
        'selfQualified',
        'selfEligible',
        'subcontractingDetails',
        'eligibilityDocuments'
    )


class Bids(Model):
    __slots__ = (
        'details',
        'statistics'
    )


class AwardCan1_1(Award):
    __slots__ = (
        'id',
        'title',
        'description',
        'status',
        'date',
        'value',
        'items',
        'contractPeriod',
        'documents'
    )


class TenderCan1_1(Tender):
    __slots__ = (
        'id',
        'title',
        'description',
        'status',
        'items',
        'value',
        'minValue',
        'procurementMethod',
        'procurementMethodRationale',
        'awardCriteria',
        'awardCriteriaDetails',
        'submissionMethod',
        'submissionMethodDetails',
        'tenderPeriod',
        'contractPeriod',
        'enquiryPeriod',
        'hasEnquiries',
        'eligibilityCriteria',
        'awardPeriod',
        'documents'
    )


class ReleaseCan1_1(Release):
    __slots__ = (
        'id',
        'date',
        'ocid',
        'language',
        'initiationType',
        'tender',
        'awards',
        'contracts',
        'bids',
        'parties',
        'tag'
    )


def release_tender_can1_1(tender, modelsMap, callbacks, prefix):
    release = ReleaseCan1_1(tender, modelsMap, callbacks, prefix).__export__()
    tag = ['tender']
    for op in ('awards', 'contracts', 'bids'):
        if op in release:
            tag.append(op[:-1])
    release['tag'] = tag
    return release


def release_tenders_can1_1(tender, modelsMap, callbacks, prefix):

    def prepare_first_tags(release):
        tag = ['tender']
        for f in ('awards', 'contracts', 'bids'):
            if f in release:
                tag.append(f[:-1])
        return list(set(tag))

    assert 'patches' in tender
    patches = tender.pop('patches')

    first_release = ReleaseCan1_1(tender, modelsMap, callbacks, prefix).__export__()
    first_release['tag'] = prepare_first_tags(first_release)
    releases = [first_release]
    for patch in patches:
        tender = jsonpatch.apply_patch(tender, patch)
        next_release = ReleaseCan1_1(tender, modelsMap, callbacks).__export__()
        if first_release != next_release:
            diff = jsonpatch.make_patch(first_release, next_release).patch
            tag = []
            for op in diff:
                if op['path'] in ['/tag', '/id']:
                    continue
                if op['op'] != 'add':
                    if not any(p in op['path'] for p in ('awards', 'contracts', 'bids')):
                        tag.append('tenderUpdate')
                    else:
                        for p in ('awards', 'contracts'):
                            if p in op['path']:
                                tag.append(p[:-1] + 'Update')
                else:
                    for p in ('awards', 'contracts', 'bids'):
                        if p in op['path']:
                            tag.append(p[:-1])
            next_release['tag'] = list(set(tag))
            releases.append(next_release)
        first_release = next_release
    return releases


def record_tenders_can1_1(tender, modelsMap, callbacks, prefix):
    releases = release_tenders_can1_1(tender, modelsMap, callbacks, prefix)
    record = {
        'releases': release_tenders_can1_1(tender, modelsMap, callbacks, prefix),
        'compiledRelease': compile_releases(releases),
        'ocid': releases[0]['ocid']
    }
    return record


def package_tenders_can1_1(tenders, modelsMap, callbacks, config):
    package = build_package(config)
    releases = []
    for tender in tenders:
        if not tender:
            continue
        if 'patches' in tender:
            releases.extend(release_tenders_can1_1(tender, config.get('prefix')))
        else:
            releases.append(release_tender_can1_1(tender, modelsMap, callbacks, config.get('prefix')))
    package['releases'] = releases
    return package


def package_records_can1_1(tenders, modelsMap, callbacks, config):
    package = build_package(config)
    records = []
    for tender in tenders:
        if not tender:
            continue
        records.append(record_tenders_can1_1(tender, modelsMap, callbacks, config.get('prefix')))
    package['records'] = records
    return package
