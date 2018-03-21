import jsonpatch
from copy import deepcopy
from openprocurement.ocds.export.models import (
    Award,
    Tender,
    Contract,
    Item,
    Value,
    Model,
    Unit,
    Document,
    callbacks,
    modelsMap,
    Release,
    Organization,
    Contact,
    Period,
    Address
)
from openprocurement.ocds.export.helpers import (
    convert_bids,
    create_auction,
    convert_unit_and_location,
    convert_cancellation_and_tenderers,
    convert_questions,
    unique_documents,
    build_package,
    compile_releases
)

extensions = {
    'bids': lambda raw_data: convert_bids(raw_data.get('bids')),
    'auctions': lambda raw_data: create_auction(raw_data),
    'items': lambda raw_data: convert_unit_and_location(raw_data.get('items')),
    'tender': lambda raw_data: convert_cancellation_and_tenderers(raw_data),
    'enquiries': lambda raw_data: convert_questions(raw_data),
    'currentStage': lambda raw_data: raw_data.get('status'),
    'procuringEntity': lambda raw_data: raw_data.get('procuringEntity'),
    'documents': lambda raw_data: unique_documents(raw_data.get('documents'), extension=True),
}


def update_callbacks():
    global callbacks
    global extensions
    callbacks_ext = deepcopy(callbacks)
    callbacks_ext.update(extensions)
    callbacks_ext.pop('tenderers', None)
    return callbacks_ext


class TenderExt(Tender):

    __slots__ = Tender.__slots__ + (
        'auctions',
        'tenderID',
        'date',
        'pendingCancellation',
        'enquiries',
        'lots',
        'procurementMethodType',
        'currentStage',
        'qualifications',
        'qualificationPeriod',
        'guarantee',
        'complaints',
        'complaintPeriod',
        'features',
        'shortlistedFirms',
        'cause',
        'causeDescription',
        'stage2TenderID',
    )


class AwardExt(Award):

    __slots__ = Award.__slots__ + (
        'lotID',
        'qualified',
        'complaints',
        'complaintPeriod',
        'eligible',
        'subcontractingDetails'
    )


class ValueExt(Value):

    __slots__ = Value.__slots__ + (
        'valueAddedTaxIncluded',
    )


class Bid(Model):

    __slots__ = (
        'id',
        'date',
        'status',
        'tenderers',
        'value',
        'documents',
        'relatedLot',
        'participationUrl',
        'selfQualified',
        'selfEligible',
        'subcontractingDetails',
        'eligibilityDocuments'
    )


class ContractExt(Contract):

    __slots__ = Contract.__slots__ + (
        'suppliers',
        'contractID',
        'contractNumber',
    )


class Auction(Model):

    __slots__ = (
        'url',
        'period',
        'minimalStep',
        'relatedLot',
    )


class UnitExt(Unit):

    __slots__ = Unit.__slots__ + (
        'id',
        'symbol',
        'scheme',
    )


class Location(Model):

    __slots__ = (
        "geometry",
    )


class ItemExt(Item):

    __slots__ = Item.__slots__ + (
        'deliveryAddress',
        'deliveryLocation',
        'relatedLot',
        'deliveryDate'
    )


class Geometry(Model):

    __slots__ = (
        'coordinates',
    )


class Enquiry(Model):

    __slots__ = (
        'id',
        'date',
        'author',
        'title',
        'description',
        'answer',
        'dateAnswered',
        'relatedItem',
    )


class DocumentExt(Document):

    __slots__ = Document.__slots__ + (
        'relatedItem',
        'documentScope',
    )


class Lot(Model):

    __slots__ = (
        'status',
        'description',
        'title',
        'value',
        'id',
        'pendingCancellation',
        'guarantee'
    )


class ReleaseExt(Release):

    __slots__ = Release.__slots__ + (
        'bids',
    )


class OrganizationExt(Organization):

    __slots__ = Organization.__slots__ + (
        'additionalContactPoints',
    )


class ProcuringEntity(OrganizationExt):

    __slots__ = OrganizationExt.__slots__ + (
        'kind',
    )


class ContactExt(Contact):

    __slots__ = Contact.__slots__ + (
        'availableLanguage',
    )


class Bids(Model):

    __slots__ = (
        'details',
    )


class Qualification(Model):

    __slots__ = (
        'status',
        'lotID',
        'description',
        'title',
        'eligible',
        'id',
        'qualified',
        'bidID',
        'date',
        'documents'
    )


class Guarantee(Model):

    __slots__ = (
        'amount',
        'currency'
    )


class Complaint(Model):

    __slots__ = (
        'status',
        'tendererActionDate',
        'satisfied',
        'tendererAction',
        'dateSubmitted',
        'id',
        'reviewPlace',
        'documents',
        'title',
        'decision',
        'acceptance',
        'dateEscalated',
        'rejectReasonDescription',
        'cancellationReason',
        'dateAnswered',
        'type',
        'relatedLot',
        'description',
        'dateCancelled',
        'date',
        'dateDecision',
        'author',
        'rejectReason',
        'resolutionType',
        'resolution',
        'reviewDate'
    )


class Feature(Model):

    __slots__ = (
        'code',
        'featureOf',
        'relatedItem',
        'title',
        'description',
        'enum'
    )


class ShortlistedFirm(Model):

    __slots__ = (
        'lots',
        'identifier',
        'name',
    )


class AddressExt(Address):

    __slots__ = Address.__slots__ + (
        'region',
    )


modelsExt = {
    'contracts': (ContractExt, []),
    'auctions': (Auction, []),
    'tender': (TenderExt, {}),
    'unit': (UnitExt, {}),
    'items': (ItemExt, []),
    'value': (ValueExt, {}),
    'enquiries': (Enquiry, []),
    'lots': (Lot, []),
    'details': (Bid, []),
    'documents': (DocumentExt, []),
    'awards': (AwardExt, []),
    'additionalContactPoints': (ContactExt, []),
    'contactPoint': (ContactExt, {}),
    'tenderers': (OrganizationExt, []),
    'suppliers': (OrganizationExt, []),
    'procuringEntity': (ProcuringEntity, {}),
    'buyer': (OrganizationExt, {}),
    'bids': (Bids, {}),
    'qualifications': (Qualification, []),
    'qualificationPeriod': (Period, {}),
    'guarantee': (Guarantee, {}),
    'complaints': (Complaint, []),
    'complaintPeriod': (Period, {}),
    'features': (Feature, []),
    'shortlistedFirms': (ShortlistedFirm, []),
    'address': (AddressExt, {}),
    'eligibilityDocuments': (DocumentExt, [])
}


def update_models_map():
    global modelsMap
    global modelsExt
    models_ext = deepcopy(modelsMap)
    models_ext.update(modelsExt)
    return models_ext


def release_tender_ext(tender, modelsMap, callbacks, prefix):
    release = ReleaseExt(tender, modelsMap, callbacks, prefix).__export__()
    tag = ['tender']
    for op in ['awards', 'contracts', 'bids']:
        if op in release:
            tag.append(op[:-1])
    release['tag'] = tag
    if 'tender' in release:
        release['tender']['date'] = tender.get('date')
    return release


def release_tenders_ext(tender, modelsMap, callbacks, prefix):

    def prepare_first_tags(release):
        tag = ['tender']
        for f in ['awards', 'contracts', 'bids']:
            if f in release:
                tag.append(f[:-1])
        return list(set(tag))

    assert 'patches' in tender
    patches = tender.pop('patches')

    first_release = ReleaseExt(tender, modelsMap, callbacks).__export__()
    first_release['tag'] = prepare_first_tags(first_release)
    releases = [first_release]
    for patch in patches:
        tender = jsonpatch.apply_patch(tender, patch)
        next_release = ReleaseExt(tender, modelsMap, callbacks).__export__()
        if first_release != next_release:
            diff = jsonpatch.make_patch(first_release, next_release).patch
            tag = []
            for op in diff:
                if op['path'] in ['/tag', '/id']:
                    continue
                if op['op'] != 'add':
                    if not any(p in op['path'] for p in ['awards', 'contracts', 'bids']):
                        tag.append('tenderUpdate')
                    else:
                        for p in ['awards', 'contracts', 'bids']:
                            if p in op['path']:
                                tag.append(p[:-1] + 'Update')
                else:
                    for p in ['awards', 'contracts', 'bids']:
                        if p in op['path']:
                            tag.append(p[:-1])
            next_release['tag'] = list(set(tag))
            releases.append(next_release)
        first_release = next_release
    return releases


def record_tenders_ext(tender, modelsMap, callbacks, prefix):
    record = {}
    record['releases'] = release_tenders_ext(tender, modelsMap, callbacks, prefix)
    record['compiledRelease'] = compile_releases(record['releases'])
    record['ocid'] = record['releases'][0]['ocid']
    return record


def package_tenders_ext(tenders, modelsMap, callbacks, config):
    package = build_package(config)
    releases = []
    for tender in tenders:
        if not tender:
            continue
        if 'patches' in tender:
            releases.extend(release_tenders_ext(tender, config.get('prefix')))
        else:
            releases.append(release_tender_ext(tender, modelsMap, callbacks, config.get('prefix')))
    package['releases'] = releases
    return package


def package_records_ext(tenders, modelsMap, callbacks, config):
    update_models_map()
    update_callbacks()
    package = build_package(config)
    records = []
    for tender in tenders:
        if not tender:
            continue
        records.append(record_tenders_ext(tender, modelsMap, callbacks, config.get('prefix')))
    package['records'] = records
    return package
