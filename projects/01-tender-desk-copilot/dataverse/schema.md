# Dataverse schema: Tender Desk

Publisher prefix `cr7a1`. Solution `TenderDesk`.

## Tender (`cr7a1_tender`)
| Column | Logical name | Type | Notes |
|---|---|---|---|
| Title | cr7a1_title | Text (200), primary | RFQ folder name, e.g. `northwind-europe-2027` |
| Shipper | cr7a1_shipper | Text (200) | |
| RFQ Folder | cr7a1_rfqfolder | Text (400) | SharePoint server-relative path |
| Received | cr7a1_received | Date only | |
| Response Due | cr7a1_responsedue | Date only | |
| Lane Count | cr7a1_lanecount | Whole number | `scope.lane_count` |
| Countries | cr7a1_countries | Text (400) | comma separated ISO codes |
| Annual Pallets | cr7a1_annualpallets | Whole number | `scope.annual_pallets_known` |
| Annual Shipments | cr7a1_annualshipments | Whole number | `scope.annual_shipments_known` |
| Hazardous Lanes | cr7a1_hazardouslanes | Whole number | |
| Gaps High / Medium / Low | cr7a1_gapshigh, cr7a1_gapsmedium, cr7a1_gapslow | Whole number | |
| Readiness % | cr7a1_readinesspct | Whole number | lanes without gaps, floor |
| Mode Bands | cr7a1_modebands | Multiline text | e.g. `FTL 9, Multimodal 8, LTL/groupage 20, Pending 3` |
| Status | cr7a1_status | Choice | Checking, Clarifying, Ready to price, Submitted |
| Owner | ownerid | Owner | solution designer |

## RFQ Lane (`cr7a1_rfqlane`)
| Column | Logical name | Type | Notes |
|---|---|---|---|
| Lane ID | cr7a1_laneid | Text (20), primary | e.g. `NW-006` |
| Tender | cr7a1_tender | Lookup (Tender) | N:1 |
| Origin / Destination | cr7a1_origin, cr7a1_destination | Text (100) | `City, CC` |
| Corridor | cr7a1_corridor | Text (10) | `PL-ES` |
| Distance km | cr7a1_distancekm | Whole number | |
| Annual Shipments | cr7a1_annualshipments | Whole number | blank when missing |
| Pallets per Shipment | cr7a1_palletspershipment | Whole number | |
| Annual Pallets | cr7a1_annualpallets | Whole number | |
| Hazardous | cr7a1_hazardous | Yes/No | |
| Incoterm | cr7a1_incoterm | Text (40) | as supplied |
| Mode Requested | cr7a1_moderequested | Text (40) | |
| Mode Suggested | cr7a1_modesuggested | Choice | FTL, Multimodal (road-rail), LTL/groupage, Pending data |
| Flags | cr7a1_flags | Text (100) | rule ids, comma separated |
| Worst Severity | cr7a1_worstseverity | Choice | High, Medium, Low, None |

## RFQ Gap (`cr7a1_rfqgap`)
| Column | Logical name | Type | Notes |
|---|---|---|---|
| Name | cr7a1_name | Autonumber, primary | `GAP-{SEQNUM:5}` |
| Tender | cr7a1_tender | Lookup (Tender) | N:1 |
| Lane | cr7a1_lane | Lookup (RFQ Lane), optional | blank for requirements gaps |
| Lane ID | cr7a1_laneid | Text (20) | denormalised for agent filters |
| Rule ID | cr7a1_ruleid | Text (5) | R01 to R09 |
| Rule Name | cr7a1_rulename | Text (100) | |
| Severity | cr7a1_severity | Choice | High, Medium, Low |
| Theme | cr7a1_theme | Text (60) | |
| Message | cr7a1_message | Multiline text | |
| Status | cr7a1_status | Choice | Open, Asked, Resolved, Accepted as assumption |

## Clarification Question (`cr7a1_clarificationquestion`)
| Column | Logical name | Type | Notes |
|---|---|---|---|
| Question | cr7a1_question | Multiline text, primary | |
| Tender | cr7a1_tender | Lookup (Tender) | N:1 |
| Theme | cr7a1_theme | Text (60) | |
| Order | cr7a1_order | Whole number | order within the letter |
| Status | cr7a1_status | Choice | Draft, Sent, Answered |
| Answer | cr7a1_answer | Multiline text | customer reply |

## Relationships
- Tender 1:N RFQ Lane (cascade delete).
- Tender 1:N RFQ Gap (cascade delete); RFQ Lane 1:N RFQ Gap (remove link on delete).
- Tender 1:N Clarification Question (cascade delete).

## Security
- Role `Tender Desk Designer`: create, read, write on all four tables at business unit level.
- Role `Tender Desk Viewer`: read only (sales, pricing).
