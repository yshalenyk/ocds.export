import jsonpatch
import itertools
from datetime import datetime
from couchdb import Database
from uuid import uuid4
from urllib import quote
from urlparse import urlparse, urlunparse
from schematics.models import Model
from schematics.types import (
    BaseType,
    StringType,
    DateTimeType,
    FloatType,
    IntType,
)
from schematics.types.serializable import serializable
from schematics.types.compound import ModelType, ListType, MultiType 
from schematics.transforms import convert, blacklist
from openprocurement.ocds.export.helpers import (
    tender_converter,
    unique_tenderers,
    unique_documents,
    patch_converter,
    now,
    generate_uri,
    get_ocid
)
from openprocurement.ocds.export.convert import Converter
from couchdb.design import ViewDefinition
from couchdb_schematics.document import SchematicsDocument


invalidsymbols = ["`","~","!", "@","#","$", '"']


class BaseModel(Model):

    class Options(object):
        serialize_when_none = False


class TenderModel(BaseModel):

    def convert(self, raw_data, strict=False, **kw):
        if 'documents' in raw_data:
            unique_documents(raw_data['documents'])
        return convert(self.__class__, raw_data, strict=False, **kw)


class Status(BaseType):
    """Only active status in standard"""

    def to_native(self, value):
        return value.split('.')[0]


class Url(BaseType):
    """Fixes invalid urls in validator"""

    def to_native(self, value, **kw):
        return ''.join(c for c in value.encode('ascii','ignore') if c not in invalidsymbols)


class Identifier(TenderModel):

    scheme = StringType()
    id = StringType()
    legalName = StringType()
    uri = Url()


class Document(TenderModel):

    id = StringType()
    documentType = StringType()
    title = StringType()
    description = StringType()
    url = Url()
    datePublished = StringType()
    dateModified = StringType()
    format = StringType()
    language = StringType()


class Classification(TenderModel):

    scheme = StringType()
    id = StringType()
    description = StringType()
    # uri = StringType()
    uri = Url() 


class Period(TenderModel):

    startDate = StringType()
    endDate = StringType()


class Value(TenderModel):

    amount = FloatType()
    currency = StringType()


class Unit(TenderModel):

    name = StringType()
    value = ModelType(Value)


class Address(TenderModel):

    streetAddress = StringType()
    locality = StringType()
    postalCode = StringType()
    countryName = StringType()


class Contact(TenderModel):

    name = StringType()
    email = StringType()
    telephone = StringType()
    faxNumber = StringType()
    url = Url()


class Organization(TenderModel):

    identifier = ModelType(Identifier)
    additionalIdentifiers = ListType(ModelType(Identifier))
    name = StringType()
    address = ModelType(Address)
    contactPoint = ModelType(Contact)


class Item(TenderModel):

    id = StringType()
    description = StringType()
    classification = ModelType(Classification)
    additionalClassifications = ListType(ModelType(Classification))
    quantity = IntType()
    unit = ModelType(Unit)


class Change(TenderModel):
    property = StringType()
    former_value = BaseType()


class Amendment(TenderModel):

    date = StringType(default=now)
    changes = ListType(ModelType(Change))
    rationale = StringType()


class Award(TenderModel, Converter):
    """See: http://standard.open-contracting.org/latest/en/schema/reference/#award"""

    id = StringType()
    title = StringType()
    description = StringType()
    status = StringType(choices=['pending', 'active', 'unsuccessful', 'cancelled'])
    date = StringType()
    value = ModelType(Value)
    suppliers = ListType(ModelType(Organization))
    items = ListType(ModelType(Item))
    contractPeriod = ModelType(Period)
    documents = ListType(ModelType(Document))
    amendment = ModelType(Amendment)


class Contract(TenderModel, Converter):
    """See: http://standard.open-contracting.org/latest/en/schema/reference/#contract"""

    id = StringType()
    awardID = StringType()
    title = StringType()
    description = StringType()
    status = StringType(choices=['pending', 'active', 'cancelled', 'terminated'])
    period = ModelType(Period)
    value = ModelType(Value)
    items = ListType(ModelType(Item))
    dateSigned = StringType()
    documents = ListType(ModelType(Document))
    amendment = ModelType(Amendment)
    

class Tender(TenderModel, Converter):
    """See: http://standard.open-contracting.org/latest/en/schema/reference/#tender"""

    _id = StringType()
    title = StringType()
    description = StringType()
    status = Status()
    items = ListType(ModelType(Item))
    minValue = ModelType(Item)
    value = ModelType(Value)
    procurementMethod = StringType()
    procurementMethodRationale = StringType()
    awardCriteria = StringType()
    awardCriteriaDetails = StringType()
    submissionMethod = ListType(StringType)
    submissionMethodDetails = StringType()
    tenderPeriod = ModelType(Period)
    enquiryPeriod = ModelType(Period)
    hasEnquiries = StringType()
    eligibilityCriteria = StringType()
    awardPeriod = ModelType(Period)
    tenderers = ListType(ModelType(Organization))
    procuringEntity = ModelType(Organization)
    documents = ListType(ModelType(Document))
    amendment = ModelType(Amendment)
    
    @serializable(serialized_name='id')
    def tender_id(self):
        return self._id 

    @serializable
    def numberOfTenderers(self):
        return len(self.tenderers) if self.tenderers else 0
    
    @classmethod
    def _convert(cls, raw_data):
        return cls(raw_data).serialize()

    def convert(self, raw_data, **kw):
        return super(Tender, self).convert(tender_converter(raw_data), **kw)


class Publisher(BaseModel):
    name = StringType()


class Release(BaseModel):

    class Options:
        roles = {
            'public': blacklist('procuringEntity')
        }

    # required by standard
    id = StringType(default=uuid4(), required=True)
    date = StringType(default=now, required=True)
    ocid = StringType(required=True)
    language = StringType(default='uk', required=True)

    # Only one choice. See: http://standard.open-contracting.org/latest/en/schema/codelists/#initiation-type
    initiationType = StringType(default='tender', choices=['tender'], required=True)

    # exported from openprocurement.api data
    procuringEntity = ModelType(Organization, serialized_name="buyer")
    tender = ModelType(Tender)
    awards = ListType(ModelType(Award))
    contracts = ListType(ModelType(Contract))
    
    @serializable(serialize_when_none=False)
    def buyer(self):
        return self.procuringEntity.to_native()

    @serializable(serialize_when_none=False)
    def tag(self):
        tags = []
        if self.tender:
            tags.append('tender')
            if hasattr(self.tender, 'amendment')\
               and getattr(self.tender, 'amendment'):
                tags.append('tenderUpdate')

        for op in ['award', 'contract']:
            field = '{}s'.format(op)
            if getattr(self, field):
                tags.append(op)
                if any([hasattr(i, 'amendment') for i in getattr(self, field, [])
                        if getattr(i, 'amendment')]):
                    tags.append('{}Update'.format(op))
        return tags

    def convert(self, raw_data, **kw):
        if all(f in raw_data for f in self._fields):
            return convert(self.__class__, raw_data, **kw)
        data = {}
        tender = raw_data.get('tender', raw_data)
        if not isinstance(tender, dict):
            tender = dict(tender)

        for f in self._fields:
            value = raw_data.get(f, '') or tender.get(f, '') 
            if value:
                data[f] = value
        data['tender'] = tender
        return convert(self.__class__, data, **kw)

    @serializable(serialize_when_none=False, serialized_name='id')
    def doc_id(self):
        if hasattr(self, '_id'):
            return self._id
        return None


class Record(BaseModel):
    releases = ListType(ModelType(Release))

    #@serializable
    #def compiledRelease(self):
    #    return get_compiled_release(self.releases)

    @serializable
    def ocid(self):
        return self.releases[0].ocid


class Package(BaseModel):

    publishedDate = StringType(default=now, required=True)
    publisher = ModelType(Publisher, required=True)
    license = StringType()
    _url = StringType(default=generate_uri)
    _policy_url = StringType()

    @serializable
    def publicationPolicy(self):
        return self._policy_url

    @serializable
    def uri(self):
        return self._url


class ReleasePackage(Package):

    releases = ListType(ModelType(Release), required=True)


class RecordPackage(Package):

    records = ListType(ModelType(Record))


class ReleaseDocument(SchematicsDocument, Release):
   pass


def clean_up(data):
    if 'amendment' in data:
        del data['amendment']
    return data


def release_tenders(tenders, prefix):
    """ returns list of Release object created from `tenders` with amendment info and ocid `prefix` """
    prev_tender = next(tenders)
    for tender in tenders:
        data = {}
        for field in ['tender', 'awards', 'contracts']:
            model = getattr(Release, field).model_class
            if field in tender:
                collection_prev = prev_tender.get(field, [])
                collection_new = tender.get(field, [])
                collection = []
                for a, b in itertools.izip_longest(collection_prev, collection_new, fillvalue={}):
                    obj = model.fromDiff(clean_up(b), clean_up(a))
                    if obj:
                        collection.append(obj)
                if collection:
                    data[field] = collection
            elif field == 'tender':
                rel = model.fromDiff(clean_up(prev_tender), clean_up(tender))
                if rel:
                    data['tender'] = rel
        if data:

            data['ocid'] = get_ocid(prefix, tender['tenderID'])
            data['_id'] = uuid4().hex
            if data:
                yield ReleaseDocument(data)
        prev_tender = tender


def release_tender(tender, prefix):
    data = {}
    for field in Release._fields:
        if field in tender and isinstance(getattr(Release, field), MultiType):
            vals = tender.get(field)
            model = getattr(Release, field).model_class
            if isinstance(vals, list):
                data[field] = [model(v) for v in vals]
            else:
                data[field] = model(vals)
        elif field == 'tender':
            model = getattr(Release, field).model_class
            data['tender'] = model(tender)
    data['ocid'] = get_ocid(prefix, tender['tenderID'])
    data['id'] = uuid4().hex
    data['date'] = tender.get('dateModified')
    return ReleaseDocument(data)


def package_tenders(tenders, params):
    data = {}
    for field in ReleasePackage._fields:
        if field in params:
            data[field] = params.get(field, '')
    data['releases'] = [release_tender(tender, params.get('prefix')) for tender in tenders]
    return ReleasePackage(dict(**data)).serialize()
