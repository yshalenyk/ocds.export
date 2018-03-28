Changes
=======

Changes between OCDS 1.0 and OCDS 1.1 standards

Release
-------

* **tag**: *planningUpdate* tag added.

  *planningUpdate*: Details of a proposed or planned contracting process are being updated. This may include addition of information and documents from consultation engagement activities, revised details or timelines for a proposed contracting process, or a tender.status update to indicate that a pipeline proposal has been withdrawn.

* **parties**: new field, array of *Organization*.
* **planning**: new field, object *Planning*.

  Information from the planning phase of the contracting process. This includes information related to the process of deciding what to contract, when and how.

Tender
------

* **parties**: new field, array of *Organization*

* **status**: *planning* and *withdraw* statuses added.

  *planning*: A future contracting process is being considered. Early information about the process may be provided in the tender section. A process with this status may provide information on early engagement or consultation opportunities, during which the details of a subsequent tender can be shaped.

  *withdraw*: No further information on this process is available under this ocid.

* **procurementMethod**: *direct* method added.
* **awardCriteria**: now can be one of the following:

  *priceOnly*, *costOnly*, *qualityOnly* or *ratedCriteria*

  *lowestCost*, *bestProposal*, *bestValueToGovernment* and *singleBidOnly* is deprecated.

  *priceOnly* replaces *lowestCost*

* **minValue**: new field, object *Value*

  The minimum estimated value of the procurement. A negative value indicates that the contracting process may involve payments from the supplier to the buyer (commonly used in concession contracts).

* **mainProcurementCategory**: new field, string, that can be one of the following

  *goods*, *works*, *services*

* **additionalProcurementCategories**: new field, array of strings, that can be one of the following:

  *goods*, *works*, *services*, *consultingServies*

  Additional categories that describe the objects of this contracting process.

* **contractPeriod**: new field, object *Period*

  The period over which the contract is estimated or required to be active.

* **milestones**: new field, object *Milestone*

Contract
--------

* **implementation**: object *Implementation*
* **milestones**: array of object *Milestone*

Organization
------------
Now called *Parties*

* **id**: new field, string
* **roles**: new field, array of strings, that can be one of the following:

  *buyer*, *procuringEntity*, *supplier*, *tenderer*, *funder*, *enquier*, *payer*, *payee*, *reviewBody*

* **details**: new field, object

  Additional classification information about parties can be provided using partyDetail extensions that define particular properties and classification schemes.

Unit
----

* **scheme**: string, that now can be one of the following:

  *UNCEFACT*, *QUDT*

  The list from which units of measure identifiers are taken. Use of the scheme ‘UNCEFACT’ for the UN/CEFACT Recommendation 20 list of ‘Codes for Units of Measure Used in International Trade’ is recommended, although other options are available.

* **uri**: new field, string in uri format

Period
------

* **maxExtentDate**: new field, string in date-time format, optional

  The period cannot be extended beyond this date. This field is optional, and can be used to express the maximum available data for extension or renewal of this period.

* **durationInDays**: new field, integer, optional

  The maximum duration of this period in days. A user interface may wish to collect or display this data in months or years as appropriate, but should convert it into days when completing this field. This field can be used when exact dates are not known. Where a startDate and endDate are given, this field is optional, and should reflect the difference between those two days. Where a startDate and maxExtentDate are given, this field is optional, and should reflect the difference between startDate and maxExtentDate.

Planning
--------

* **milestones**: object *Milestone*
* **documents**: deleted

Milestone
---------

* **type**: new field, string, that can be one of the following:

  *preProcurement*, *approval*, *engagement*, *assessment*, *delivery*, *reporting*, *financing*

Transaction
-----------

* **value**: new field, object *Value* - replacing amount
* **payer**: new field, *Organization* reference - replacing providerOrganization
* **payee**: new field, *Organization* reference - replacing receiverOrganization

Extensions
==========

Release
-------

* **title**: new field, string
* **description**: new field, string
* **lots**: new field, array of object *Lot*

Tender
------

* **participationFees**: new field, array of object *ParticipationFee*

Award
-----

* **relatedLots**: new field, array of string
* **relatedBid**: new field, string

Bids
----

* **bidStatistics**: new field, array of object *BidsStatistic*

Document
--------

* **relatedLots**: new field, array of string

Item
----

* **relatedLot**: new field, object *Lot*

Milestone
---------

* **relatedLots**: new field, array of string

Enquiry
-------

* **relatedLot**: new field, string
* **threadID**: new field, string

Location
--------

* **description**: new field, string
* **uri**: new field, string

Geometry
--------

* **type**: new field, string

New entities
============

ParticipationFee
----------------
Where a tender process involves payment of fees to access documents, submit a proposal, or be awarded a contract, this extension can be used to provide fee details.

* **type** - string, that can be one of the following:

  *document*, *deposit*, *submission*, *win*

* **value** - object *Value*
* **description** - string, optional
* **methodOfPayment** - array of strings, optional
