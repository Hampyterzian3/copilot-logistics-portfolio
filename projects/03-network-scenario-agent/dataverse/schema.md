# Dataverse schema

Publisher prefix `cr_`. Solution: Network Scenario Agent.

## cr_networkscenario (Network Scenario)
| Column | Type | Notes |
|---|---|---|
| cr_name | Text (autonumber `NS-{SEQNUM:4}`) | Primary name |
| cr_requestedby | Lookup (User) | Who asked the agent |
| cr_runon | Date and time | |
| cr_fuelindex | Decimal (2) | Diesel cost index |
| cr_co2price | Currency | EUR per tonne |
| cr_handlingldm | Currency | EUR per loading metre |
| cr_maxstops | Whole number | |
| cr_activehubs | Text | Comma-separated hub ids |
| cr_recommended | Choice: Direct, Milk-run, Cross-dock, Best mix | |
| cr_savingpct | Decimal (2) | Best mix vs cheapest single design |
| cr_recommendationtext | Multiline text | From the API |

## cr_scenariodesignresult (Scenario Design Result)
| Column | Type | Notes |
|---|---|---|
| cr_name | Text | e.g. NS-0001 bestmix |
| cr_scenario | Lookup (cr_networkscenario) | N:1, cascade delete |
| cr_design | Choice: Direct, Milk-run, Cross-dock, Best mix | |
| cr_costweek | Currency | EUR |
| cr_co2tweek | Decimal (4) | Tonnes |
| cr_truckstweek | Whole number | All legs |
| cr_plantarrivals | Whole number | |
| cr_vkmweek | Decimal (1) | |

## cr_suppliermode (Supplier Mode)
| Column | Type | Notes |
|---|---|---|
| cr_name | Text | Supplier id |
| cr_scenario | Lookup (cr_networkscenario) | N:1, cascade delete |
| cr_supplier | Lookup (cr_supplier) | N:1 |
| cr_mode | Choice: Direct, Milk-run, Cross-dock | Best-mix choice |
| cr_hubid | Text | Hub when cross-dock |

## cr_supplier (Supplier, reference data)
| Column | Type | Notes |
|---|---|---|
| cr_name | Text | S01 to S60 |
| cr_region | Text | e.g. DE-S, IT-N |
| cr_latitude, cr_longitude | Float | For the Power BI map |
| cr_ldmweek | Decimal (2) | Weekly loading metres |
| cr_frequency | Whole number | Shipments per week |
| cr_tperldm | Decimal (2) | Tonnes per loading metre |

Relationships: Network Scenario 1:N Scenario Design Result; Network Scenario 1:N Supplier Mode; Supplier 1:N Supplier Mode. Power BI reads Supplier Mode joined to Supplier for the flow map.
