# Power Fx formulas: Toll Surcharge Recovery canvas app

Data sources: Dataverse `Customers`, `Shipments`, `Lanes`, `TollRates`, `SurchargeProposals`, environment variables. The maths mirrors `src/toll.py`. Toll rates are ILLUSTRATIVE in this project.

## App.Formulas (named formulas)
```powerfx
TruckPallets = 33;
TruckPayloadKg = 24000;
TierAutoMaxPct = Value(LookUp('Environment Variable Values', 'Environment Variable Definition'.'Schema Name' = "cl_TierAutoMaxPct").Value);
TierCmMaxPct   = Value(LookUp('Environment Variable Values', 'Environment Variable Definition'.'Schema Name' = "cl_TierCmMaxPct").Value);
TierAutoMaxEur = 200;
TierCmMaxEur   = 500;

// Toll per shipment = tolled km x rate(CO2 class, weight class) x share of truck
ShipmentToll(s: Record): Number =
    s.Lane.'Tolled km' *
    LookUp(TollRates, 'CO2 class' = s.'CO2 class' && 'Weight class' = s.'Weight class').'EUR per km' *
    Min(1, If(s.Customer.'Allocation basis' = 'Allocation basis (Customers)'.Pallet,
              s.Pallets / TruckPallets,
              s.'Weight kg' / TruckPayloadKg));

ApprovalTier(incPct: Number, eur: Number): Text =
    If(incPct <= TierAutoMaxPct && eur <= TierAutoMaxEur, "Auto-approved",
       incPct <= TierCmMaxPct && eur <= TierCmMaxEur, "Commercial manager",
       "Steering committee");
```

## Screen OnVisible: per-customer impact (cached collection)
`Shipments.'Toll EUR'` is pre-calculated by the recalculation flow, so the aggregate is delegable.
```powerfx
ClearCollect(
    colImpact,
    AddColumns(
        GroupBy(Shipments, Customer, Rows),
        Code,       ThisRecord.Customer.Code,
        Industry,   ThisRecord.Customer.Industry,
        Shipments,  CountRows(Rows),
        Revenue,    Sum(Rows, 'Revenue EUR'),
        Cost,       Sum(Rows, 'Cost EUR'),
        Km,         Sum(Rows, Lane.'Distance km'),
        Toll,       Sum(Rows, 'Toll EUR')
    )
);
Set(varMethod, "pct"); Set(varRecovery, 100);
```

## galCustomers.Items (search + sort)
```powerfx
SortByColumns(
    Filter(colImpact, IsBlank(txtSearch.Text) || txtSearch.Text in Code || txtSearch.Text in Industry),
    Switch(drpSort.Selected.Value, "Toll impact", "Toll", "% of freight", "TollPct", "Code"),
    If(drpSort.Selected.Value = "Code", SortOrder.Ascending, SortOrder.Descending)
)
```
Label in the gallery row: `Text(ThisItem.Toll / ThisItem.Revenue, "0.0%")`.

## Proposal (more App.Formulas named formulas; they recalculate when the selection, slider or method changes)
```powerfx
// varRecovery from sldRecovery.Value, varMethod from the segmented buttons
locTarget = galCustomers.Selected.Toll * varRecovery / 100;
locUnit = Switch(varMethod,
    "flat", Round(locTarget / galCustomers.Selected.Shipments, 2),
    "pct",  Round(locTarget / galCustomers.Selected.Revenue * 100, 2),
    "km",   Round(locTarget / galCustomers.Selected.Km, 3));
locSurcharge = Switch(varMethod,
    "flat", locUnit * galCustomers.Selected.Shipments,
    "pct",  galCustomers.Selected.Revenue * locUnit / 100,
    "km",   locUnit * galCustomers.Selected.Km);
locIncreasePct = locSurcharge / galCustomers.Selected.Revenue * 100;
locMarginBefore = galCustomers.Selected.Revenue - galCustomers.Selected.Cost;
locMarginAfter  = locMarginBefore - galCustomers.Selected.Toll + locSurcharge;
locTier = ApprovalTier(locIncreasePct, locSurcharge);
```
Power Fx `Round` rounds half away from zero, which equals the half-up rounding in `toll.py` for positive values.

## btnSubmit.OnSelect (Patch + start the approval flow)
```powerfx
With(
    { p: Patch(
        SurchargeProposals,
        Defaults(SurchargeProposals),
        {
            Customer:        LookUp(Customers, Code = galCustomers.Selected.Code),
            Method:          Switch(varMethod, "flat", 'Method (SurchargeProposals)'.'Flat per shipment',
                                               "pct",  'Method (SurchargeProposals)'.'% of freight',
                                                       'Method (SurchargeProposals)'.'Per km'),
            'Recovery %':    varRecovery,
            'Unit rate':     locUnit,
            'Toll EUR':      galCustomers.Selected.Toll,
            'Surcharge EUR': locSurcharge,
            'Increase %':    locIncreasePct,
            'Margin % before': locMarginBefore / galCustomers.Selected.Revenue * 100,
            'Margin % after':  locMarginAfter / (galCustomers.Selected.Revenue + locSurcharge) * 100,
            Tier:   Switch(locTier, "Auto-approved", 'Tier (SurchargeProposals)'.'Auto-approved',
                                    "Commercial manager", 'Tier (SurchargeProposals)'.'Commercial manager',
                                    'Tier (SurchargeProposals)'.'Steering committee'),
            Status: 'Status (SurchargeProposals)'.Submitted
        }) },
    TollSurchargeApproval.Run(Text(p.SurchargeProposal));
    Notify("Submitted: " & locTier, NotificationType.Success)
)
```

## Dashboard tab
The tab hosts a Power BI tile (`PowerBIIntegration` / Power BI tile control) bound to the steering report, filtered to the selected customer:
```powerfx
"https://app.powerbi.com/reportEmbed?reportId=<id>&filter=Customers/Code eq '" & galCustomers.Selected.Code & "'"
```

## Copilot control
Add the Copilot control (preview) to the screen, data source `SurchargeProposals` and `Shipments`, with the description "Explain a customer's toll impact, recovery options and approval tier. Rates are illustrative."
