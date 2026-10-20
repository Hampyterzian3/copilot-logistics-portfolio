# Knowledge sources

| Source | Type | Purpose |
|---|---|---|
| Dataverse: Customers, Shipments, Lanes, TollRates, SurchargeProposals | Dataverse knowledge + tools | Per-customer toll, revenue, margin, proposal status |
| `Toll surcharge policy.docx` (SharePoint, Commercial > Pricing) | SharePoint | Recovery methods, tier thresholds, phasing rules, wording for customer letters |
| `Toll rate table` (SharePoint list maintained by Pricing) | SharePoint | Rate per CO2 class and weight class with validity dates. Illustrative values in this project |
| `Customer letter templates` (SharePoint) | SharePoint | Approved text to announce a surcharge |

Tools (Power Automate flows exposed as agent actions):
- **Get customer impact** (input: customer code): returns shipments, tolled km, toll EUR, toll % of freight, margin before and after, top lanes.
- **Get proposal** (input: customer code): latest SurchargeProposals row with method, unit rate, tier, status.

Not used: public web search (answers must come from the governed Dataverse data and policy).
