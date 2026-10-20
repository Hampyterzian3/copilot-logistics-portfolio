# Dataverse schema

Dataverse holds the outputs of each Monday run and the approval trail. KPI facts stay in the Power BI semantic model; Dataverse stores only the exported variances, generated text and status. Publisher prefix `kpi_`.

## kpi_weeklyvariance (one row per flagged customer x KPI x week)

| Column | Type | Notes |
|---|---|---|
| kpi_weeklyvarianceid | Unique identifier | Primary key |
| kpi_name | Text (100) | Primary name: `2026-W39 Northwind Automotive Revenue` |
| kpi_week | Text (8) | ISO week label |
| kpi_customer | Lookup > kpi_customer | |
| kpi_kpi | Choice | Shipments, Revenue, Cost to serve, Margin, On-time, Claims, CO2 per shipment |
| kpi_value | Decimal | This week |
| kpi_baseline | Decimal | Median of previous 8 weeks |
| kpi_wow | Decimal | Relative or pp, see kpi_kind |
| kpi_vsbaseline | Decimal | Relative or pp |
| kpi_kind | Choice | rel, pp, abs |
| kpi_zscore | Decimal | Robust z (MAD) |
| kpi_score | Decimal | Materiality score |
| kpi_tag | Choice | High, Medium, Low |
| kpi_favourable | Yes/No | |
| kpi_rank | Whole number | 1 = most material |
| kpi_factid | Text (6) | `F09`, used as source tag in generated text |
| kpi_measure | Text (100) | DAX measure name, for example `Revenue vs Baseline %` |
| kpi_brief | Lookup > kpi_briefdraft | |

## kpi_briefdraft (one row per week)

| Column | Type | Notes |
|---|---|---|
| kpi_briefdraftid | Unique identifier | Primary key |
| kpi_week | Text (8) | Primary name, alternate key |
| kpi_headline | Multiline text | With refs |
| kpi_briefjson | Multiline text (max) | Headline, three things, callouts, actions; each sentence `{text, refs}` |
| kpi_slidesjson | Multiline text | Five slides `{n, title, visual, bullets}` |
| kpi_teamstext | Multiline text | Teams card body |
| kpi_worddrafturl | URL | Word draft in SharePoint |
| kpi_deckoutlineurl | URL | Deck outline file |
| kpi_sentencecount | Whole number | |
| kpi_validation | Choice | Passed, Blocked |
| kpi_status | Choice | Draft, Approved, Rejected, Failed |
| kpi_approver | Lookup > systemuser | Set on approval |
| kpi_approvedon | Date and time | |
| kpi_reviewcomments | Multiline text | From the approval response |

## kpi_customer (reference, synced from CRM)

| Column | Type | Notes |
|---|---|---|
| kpi_customerid | Unique identifier | Primary key |
| kpi_name | Text (100) | Fictional names in the demo (Northwind Automotive, Fabrikam Steel, ...) |
| kpi_code | Text (3) | NWA, FBS, TSR, LWC, AWC, WGP |
| kpi_industry | Text (60) | Generic industry only |
| kpi_accountlead | Lookup > systemuser | Owner role for actions |

## Relationships
- kpi_customer 1:N kpi_weeklyvariance
- kpi_briefdraft 1:N kpi_weeklyvariance
- systemuser 1:N kpi_briefdraft (approver)

## Security
- Role "KPI Brief Analyst": read/write kpi_briefdraft (business unit), read kpi_weeklyvariance.
- Role "KPI Brief Flow": create on both tables (application user for the flow).
- Leadership has no Dataverse access; they receive only the approved Teams post and files.
