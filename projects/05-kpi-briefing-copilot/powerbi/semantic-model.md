# Semantic model: Contoso Account KPIs (weekly)

One governed Power BI semantic model is the single source for the dashboard, the Monday variance export and every number the agent writes. The agent never reads raw operational tables.

## Tables

| Table | Grain | Key columns | Source |
|---|---|---|---|
| `FactWeeklyKPI` | customer x week | CustomerKey, WeekKey, Shipments, RevenueEUR, CostEUR, OnTimeShipments, Claims, CO2Kg | Certified dataflow from TMS, finance and claims systems (demo: `data/kpi_weekly.csv`) |
| `DimCustomer` | customer | CustomerKey, CustomerName, Industry, AccountLead (UPN), Region | Master data (CRM) |
| `DimWeek` | ISO week | WeekKey, WeekLabel (`2026-W39`), WeekEnd, WeekIndex (contiguous integer) | Generated calendar |
| `Thresholds` | KPI | KPI, Kind (rel / pp / abs), Threshold, Weight, Better (up / down) | Maintained by analytics, change-controlled |
| `_Measures` | n/a | home table for all DAX measures | `measures.dax` |

Relationships: `FactWeeklyKPI[CustomerKey]` many-to-one `DimCustomer`, `FactWeeklyKPI[WeekKey]` many-to-one `DimWeek`, single direction. `Thresholds` is disconnected (read with `LOOKUPVALUE`).

## Measure families

| Family | Measures | Notes |
|---|---|---|
| Base KPIs | Shipments, Revenue, Cost to Serve per Shipment, Margin %, OTP %, Claims, CO2 kg per Shipment | Ratios computed from sums, never averaged across customers |
| Week on week | `<KPI> WoW %` or `WoW pp` | Previous `WeekIndex` |
| Baseline | `<KPI> Baseline`, `<KPI> Spread`, `<KPI> vs Baseline % / pp`, `<KPI> Z` | Median of previous 8 weeks; spread = 1.4826 x MAD so one event week does not hide the next |
| Flags | `<KPI> Flag` | Threshold breached **and** abs(z) >= 2 |
| Materiality | `<KPI> Materiality Score`, `Materiality Tag` | min(abs(z), 8) x KPI weight x sqrt(revenue share x 6); High >= 5, Medium >= 3 |
| Margin bridge | Revenue per Shipment Baseline, Cost per Shipment Baseline, Margin Rate Effect pp, Margin Cost Effect pp | Pooled 8 weeks; the two effects sum exactly to the pooled margin change |

Units: in DAX, `Margin %` and `OTP %` are fractions formatted as percentages; `pp` measures are multiplied by 100. The Python reference (`src/briefing.py`) stores them as percentages.

## Thresholds (default)

| KPI | Kind | Threshold | Weight | Better |
|---|---|---|---|---|
| Shipments | rel | 10% | 0.7 | up |
| Revenue | rel | 10% | 0.9 | up |
| Cost to Serve per Shipment | rel | 4% | 0.8 | down |
| Margin % | pp | 2.0 | 1.0 | up |
| OTP % | pp | 2.0 | 0.9 | up |
| Claims | abs | 5 | 0.6 | down |
| CO2 kg per Shipment | rel | 6% | 0.5 | down |

## Governance

- Endorsed as **Certified** in the Power BI service; workspace owned by Analytics, viewers via Entra ID group.
- Row-level security role `AccountLead`: `DimCustomer[AccountLead] = USERPRINCIPALNAME()`. Executives and the flow's service principal use the unrestricted role.
- Sensitivity label "Confidential: commercial" flows into the exported Word and PowerPoint drafts.
- The flow queries the model through the Power BI REST `executeQueries` endpoint (DAX below). The same measure names appear as source tags in every generated sentence.

## Export query used by the Monday flow

```dax
DEFINE
    VAR _week = CALCULATE ( MAX ( DimWeek[WeekIndex] ), FactWeeklyKPI )   // latest loaded week
EVALUATE
CALCULATETABLE (
    ADDCOLUMNS (
        SUMMARIZE ( FactWeeklyKPI, DimCustomer[CustomerName] ),
        "Revenue", [Revenue], "RevenueVsBase", [Revenue vs Baseline %], "RevenueZ", [Revenue Z],
        "MarginPct", [Margin %], "MarginVsBasePP", [Margin % vs Baseline pp], "MarginZ", [Margin % Z],
        "OTP", [OTP %], "OTPVsBasePP", [OTP % vs Baseline pp], "OTPZ", [OTP % Z],
        "Shipments", [Shipments], "ShipmentsVsBase", [Shipments vs Baseline %], "ShipmentsZ", [Shipments Z],
        "MarginScore", [Margin Materiality Score], "OTPScore", [OTP Materiality Score],
        "ShipmentsScore", [Shipments Materiality Score]
    ),
    DimWeek[WeekIndex] = _week
)
```
