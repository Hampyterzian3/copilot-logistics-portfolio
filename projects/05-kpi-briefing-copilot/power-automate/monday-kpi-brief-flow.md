# Flow: KPI Brief, Monday run

Scheduled cloud flow. Exports the week's variances from the governed semantic model, drafts the brief, deck outline and Teams post, and waits for an analyst to approve before anything reaches leadership.

## Trigger
- **Recurrence**: every Monday 06:00, time zone W. Europe Standard Time.
- Precondition: the dataset refresh finished (checked in step 2), so the brief never uses a partial week.

## Connections
- Power BI (service principal with Build permission on the certified dataset)
- Microsoft Dataverse
- Word Online (Business), OneDrive for Business / SharePoint
- Approvals, Microsoft Teams
- Copilot Studio (agent action: "Draft brief text")

## Actions

| # | Action | Detail |
|---|---|---|
| 1 | Initialize variable `weekLabel` | `formatDateTime(addDays(utcNow(), -1), 'yyyy')` and ISO week from the `DimWeek` lookup (step 3) |
| 2 | Power BI: Get refresh history | Dataset "Contoso Account KPIs"; condition `equals(first(body('Get_refresh_history')?['value'])?['status'], 'Completed')`, else terminate with status Failed and notify the analytics channel |
| 3 | Power BI: Run a query against a dataset | DAX export query from `powerbi/semantic-model.md` (one row per customer x KPI with value, baseline, vs baseline, z, score, tag) |
| 4 | Filter array `flagged` | `@equals(item()?['[Flag]'], true)` |
| 5 | Select + sort | Order by `[Score]` descending; add `rank` = `add(indexOf(...), 1)` |
| 6 | Apply to each: Dataverse Add a new row `kpi_weeklyvariance` | Week, customer, KPI, value, baseline, vs baseline, z, score, tag, fact id `concat('F', formatNumber(add(iterationIndexes('Apply_to_each'), 1), '00'))` |
| 7 | Run the brief generator | Copilot Studio agent action "Draft brief text" with the flagged rows and portfolio totals as JSON. Its template rules match `src/briefing.py`: every sentence returns with `refs`. |
| 8 | Condition: traceability check | Child flow "Validate brief": every sentence has at least one ref, every ref exists in the export, every number in the sentence appears in a referenced row. If any check fails, set status `Blocked` and stop |
| 9 | Word Online: Populate a Microsoft Word template | Template `Weekly brief.dotx` in SharePoint; fields headline, summary, things, callouts, actions, sources table. Save as `Briefs/Weekly account brief {weekLabel}.docx` |
| 10 | Create file | `Briefs/Deck outline {weekLabel}.docx` (five slide headings, bullets, speaker notes with refs) for "Create presentation from file" in PowerPoint with Microsoft 365 Copilot |
| 11 | Dataverse Add a new row `kpi_briefdraft` | Status `Draft`, links to both files, Teams text, sentence count |
| 12 | Start and wait for an approval | Type "Approve/Reject, first to respond"; assigned to the commercial analyst group; details = headline + three things + links |
| 13 | Condition: outcome is Approve | **Yes**: Teams Post adaptive card in channel "Leadership weekly" as the flow bot; update `kpi_briefdraft` status `Approved`, approver, timestamp. **No**: update status `Rejected` with comments, post the comments back to the analyst chat |

## Key expressions

```text
ISO week label     concat(string(body('Get_week')?['Year']), '-W', formatNumber(body('Get_week')?['IsoWeek'], '00'))
Flag               and(greaterOrEquals(abs(item()?['[VsBase]']), item()?['[Threshold]']), greaterOrEquals(abs(item()?['[Z]']), 2))
Materiality tag    if(greaterOrEquals(item()?['[Score]'], 5), 'High', if(greaterOrEquals(item()?['[Score]'], 3), 'Medium', 'Low'))
Approved?          equals(outputs('Start_and_wait_for_an_approval')?['body/outcome'], 'Approve')
```

## Errors and retries
- Steps 2 and 3: retry policy exponential, 4 attempts.
- Scope "Try" around steps 3 to 11, "Catch" posts the run URL to the analytics channel and sets status `Failed`.
- No step sends anything to leadership before step 13.

## Child flows called by the agent topics
| Flow | Topic | Returns |
|---|---|---|
| KPI Brief: get week (`...0501`) | Weekly brief | brief JSON, Word and deck links, flagged count |
| KPI Brief: margin bridge (`...0502`) | Why did margin move | margin, baseline, rate and cost effects, per-shipment values, tag |
| KPI Brief: slide outline (`...0503`) | Build slide outline | slides JSON, deck link |
| KPI Brief: compare (`...0504`) | Compare customers | one row per customer vs baseline |
