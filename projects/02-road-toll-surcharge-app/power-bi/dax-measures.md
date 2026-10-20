# Power BI steering dashboard: DAX measures

Model: Dataverse tables `Shipments` (fact), `Customers`, `Lanes`, `TollRates`, `SurchargeProposals`, plus a disconnected `RecoveryPct` parameter table (`GENERATESERIES(0, 120, 5)`). Toll rates are ILLUSTRATIVE in this project.

```dax
Freight Revenue = SUM ( Shipments[cl_revenueeur] )
Freight Cost    = SUM ( Shipments[cl_costeur] )
Toll Cost       = SUM ( Shipments[cl_tolleur] )

Toll % of Freight = DIVIDE ( [Toll Cost], [Freight Revenue] )

Margin Before Toll = [Freight Revenue] - [Freight Cost]
Margin % Before Toll = DIVIDE ( [Margin Before Toll], [Freight Revenue] )
Margin % Toll Absorbed = DIVIDE ( [Margin Before Toll] - [Toll Cost], [Freight Revenue] )

Selected Recovery % = SELECTEDVALUE ( RecoveryPct[Value], 100 ) / 100

Surcharge What-If = [Toll Cost] * [Selected Recovery %]
Margin % With Surcharge =
    DIVIDE (
        [Margin Before Toll] - [Toll Cost] + [Surcharge What-If],
        [Freight Revenue] + [Surcharge What-If]
    )

Margin Erosion pts = ( [Margin % Before Toll] - [Margin % Toll Absorbed] ) * 100

-- Proposals actually submitted through the app
Proposed Surcharge = SUM ( SurchargeProposals[cl_surchargeeur] )
Approved Surcharge =
    CALCULATE ( [Proposed Surcharge], SurchargeProposals[cl_status] = "Approved" )
Recovery Rate Approved = DIVIDE ( [Approved Surcharge], [Toll Cost] )

Customers Without Proposal =
    COUNTROWS (
        FILTER ( Customers, CALCULATE ( COUNTROWS ( SurchargeProposals ) ) = 0 && [Toll Cost] > 0 )
    )

Steering Cases =
    CALCULATE ( COUNTROWS ( SurchargeProposals ), SurchargeProposals[cl_tier] = "Steering committee" )

-- Ranking for the "Top 10 customers by toll impact" bar chart (visual filter: Rank <= 10)
Toll Rank =
    RANKX ( ALLSELECTED ( Customers ), [Toll Cost], , DESC, DENSE )

-- Share of toll from CO2 class 1 and 2 trucks (fleet renewal lever)
Toll From High Emission % =
    DIVIDE ( CALCULATE ( [Toll Cost], Shipments[cl_co2class] <= 2 ), [Toll Cost] )
```

## Report pages
1. **Steering overview**: KPI cards (Toll Cost, Toll % of Freight, Margin % Before Toll vs Toll Absorbed vs With Surcharge, Recovery Rate Approved), top 10 bar by `Toll Cost` with `Toll Rank <= 10`, tier donut by `SurchargeProposals[cl_tier]`.
2. **Customer drill-through**: lanes, CO2 class mix, method comparison.
3. **Pipeline**: proposals by status and tier, ageing of open approvals.

Row-level security: commercial managers see their own accounts (`Customers[cl_accountowner] = USERPRINCIPALNAME()`), the steering committee sees all.
