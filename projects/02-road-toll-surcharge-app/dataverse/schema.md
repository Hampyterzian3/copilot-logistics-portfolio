# Dataverse schema: Road-Toll Surcharge Recovery

Publisher prefix `cl_` (Contoso Logistics). All tables are organisation-owned except SurchargeProposals (user-owned, so the submitter is the owner).

## cl_Customer (Customers)
| Column | Type | Notes |
|---|---|---|
| cl_customerid | Unique identifier | Primary key |
| cl_code | Text (10), primary name | e.g. `C006` |
| cl_name | Text (100) | |
| cl_industry | Choice | Automotive OEM, Steel manufacturer, Retail chain, ... |
| cl_allocationbasis | Choice | `Pallet` (pallet places / 33) or `Weight` (kg / 24,000) |
| cl_accountowner | Lookup (User) | Commercial manager who approves tier 2 |

## cl_Lane (Lanes)
| Column | Type | Notes |
|---|---|---|
| cl_laneid | Unique identifier | |
| cl_code | Text, primary name | `L01` |
| cl_name | Text | `Port terminal to DC North` |
| cl_distancekm | Decimal (1) | Total lane distance |
| cl_tolledkm | Decimal (1) | Km on tolled roads |
| cl_tolledshare | Formula column (Decimal) | `cl_tolledkm / cl_distancekm` |

## cl_TollRate (TollRates)
ILLUSTRATIVE in this project. In production the official tariff is loaded here by the pricing team, with validity dates.
| Column | Type | Notes |
|---|---|---|
| cl_tollrateid | Unique identifier | |
| cl_name | Text, primary name | `3|W4` |
| cl_co2class | Whole number (1-5) | 1 highest emitting, 5 zero emission |
| cl_weightclass | Choice | W1 3.5-12 t, W2 12-18 t, W3 18-32 t, W4 over 32 t |
| cl_eurperkm | Currency (3 dp) | |
| cl_validfrom / cl_validto | Date only | |

Alternate key: (cl_co2class, cl_weightclass, cl_validfrom).

## cl_Shipment (Shipments)
| Column | Type | Notes |
|---|---|---|
| cl_shipmentid | Unique identifier | |
| cl_code | Text, primary name | `S00001` |
| cl_customer | Lookup (cl_Customer) | N:1 |
| cl_lane | Lookup (cl_Lane) | N:1 |
| cl_co2class | Whole number | Truck CO2 emission class |
| cl_weightclass | Choice | Truck weight class |
| cl_pallets | Whole number | |
| cl_weightkg | Whole number | |
| cl_revenueeur / cl_costeur | Currency | |
| cl_tolleur | Currency | Written by the recalculation flow or the Python batch (toll.py) |

## cl_SurchargeProposal (SurchargeProposals)
| Column | Type | Notes |
|---|---|---|
| cl_surchargeproposalid | Unique identifier | |
| cl_name | Autonumber | `SP-{SEQNUM:5}` |
| cl_customer | Lookup (cl_Customer) | N:1 |
| cl_method | Choice | Flat per shipment, % of freight, Per km |
| cl_recoverypct | Whole number (0-150) | |
| cl_unitrate | Decimal (3) | EUR/shipment, % or EUR/km |
| cl_tolleur / cl_surchargeeur | Currency | |
| cl_increasepct | Decimal (2) | Surcharge / freight revenue |
| cl_marginpctbefore / cl_marginpctafter | Decimal (2) | |
| cl_tier | Choice | Auto-approved, Commercial manager, Steering committee |
| cl_status | Choice | Draft, Submitted, Approved, Rejected |
| cl_approvalcomments | Multiline text | From the approval flow |

## Relationships
- Customer 1:N Shipment, Customer 1:N SurchargeProposal, Lane 1:N Shipment.
- TollRate is looked up by (co2 class, weight class, date), not by relationship, so rate changes do not cascade into history.

## Environment variables
`cl_TierAutoMaxPct` (3.5), `cl_TierAutoMaxEur` (200), `cl_TierCmMaxPct` (5.0), `cl_TierCmMaxEur` (500), `cl_SteeringCommitteeGroup` (Teams/Entra group id).
