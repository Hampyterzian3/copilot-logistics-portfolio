# Dataverse schema (publisher prefix `cr_`)

## cr_shipmentrisk (Shipment Risk), one row per inbound shipment
| Column | Type | Notes |
|---|---|---|
| cr_shipmentid | Text (20), alternate key | e.g. CTL-261556 |
| cr_customer | Lookup -> cr_customer | |
| cr_carrier | Lookup -> cr_carrier | |
| cr_lane | Lookup -> cr_lane | |
| cr_area | Lookup -> cr_postcodearea | destination area |
| cr_poref | Text (20) | customer order reference |
| cr_pieces | Whole number | |
| cr_status | Choice: in_transit, delivered, lost, cancelled | |
| cr_promisedon | Date and time | |
| cr_lastscanlabel, cr_lastscanlocation | Text | from latest cr_scanevent |
| cr_lastscanon | Date and time | |
| cr_dwellnormhours | Decimal | normal dwell for the last scan type |
| cr_customsstatus | Choice: not_required, pending, held, cleared | |
| cr_remainingtransitdays | Decimal | from lane transit norm and milestone |
| cr_nonworkingdays | Whole number | weekend and holiday days before promised date |
| cr_holidayname | Text | blank if none |
| cr_score | Whole number (0-100) | |
| cr_band | Choice: critical, at_risk, watch, on_track | |
| cr_previousband | Choice (same) | used to detect new critical |
| cr_points | Multiline text (JSON) | points per factor |
| cr_topreason | Text (300) | rank 1 reason, for lists |
| cr_scoredon | Date and time | |
| cr_waslate | Yes/No | set on delivery, used by the backtest |

## cr_riskreason (Risk Reason), 0-3 per shipment per run
| Column | Type |
|---|---|
| cr_shipment | Lookup -> cr_shipmentrisk |
| cr_rank | Whole number (1-3) |
| cr_factor | Choice: lane, area, carrier, dwell, customs, slack, calendar |
| cr_points | Decimal |
| cr_text | Text (300) |

## cr_scanevent (Scan Event)
| Column | Type |
|---|---|
| cr_eventid | Text, alternate key |
| cr_shipment | Lookup -> cr_shipmentrisk |
| cr_eventcode | Choice: PICKED_UP, DEPARTED_ORIGIN_HUB, ARRIVED_CROSS_DOCK, CUSTOMS_LODGED, DEPARTED_CROSS_DOCK, ARRIVED_DEST_DEPOT, OUT_FOR_DELIVERY, DELIVERED |
| cr_location | Text |
| cr_eventon | Date and time |

## cr_riskalert (Risk Alert)
| Column | Type |
|---|---|
| cr_shipment | Lookup -> cr_shipmentrisk |
| cr_teamsmessageid | Text |
| cr_status | Choice: open, acknowledged, escalated, closed |
| cr_acknowledgedby | Lookup -> systemuser |
| cr_acknowledgedon, cr_escalatedon | Date and time |
| cr_customerdraft, cr_carrierdraft | Multiline text |

## Reference tables (refreshed nightly from closed shipments, last 12 months)
- **cr_lane**: cr_name (e.g. `TR-BUR > BE`), cr_origin, cr_destcountry, cr_customsrequired (Yes/No), cr_basetransitdays (Decimal), cr_delayrate (Decimal 0-1).
- **cr_postcodearea**: cr_code (e.g. `BE-Z03`), cr_country, cr_shipments12m (Whole number), cr_lossrate (Decimal 0-1).
- **cr_carrier**: cr_name, cr_ontimerate (Decimal 0-1), cr_opsemail (Email).
- **cr_customer**: cr_name, cr_servicecontact (Email).
- **cr_riskrunlog**: cr_startedon, cr_finishedon, cr_eventsread, cr_shipmentsscored, cr_newcritical, cr_error.

## Relationships
- cr_customer 1:N cr_shipmentrisk; cr_carrier 1:N cr_shipmentrisk; cr_lane 1:N cr_shipmentrisk; cr_postcodearea 1:N cr_shipmentrisk.
- cr_shipmentrisk 1:N cr_riskreason (cascade delete), 1:N cr_scanevent, 1:N cr_riskalert.

## Security
- Control tower role: read/write cr_shipmentrisk, cr_riskalert; read others.
- Customer service role: read cr_shipmentrisk and cr_riskreason for their business unit's customers only.
