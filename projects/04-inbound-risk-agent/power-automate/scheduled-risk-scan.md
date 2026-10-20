# Flow: Inbound Risk - Scheduled scan (every 30 minutes)

Pulls new tracking events, scores every open inbound shipment and posts a Teams alert for each new critical one.

## Trigger
- **Recurrence**: interval 30, frequency Minute, time zone W. Europe Standard Time.
- Concurrency control on, degree of parallelism 1 (a run never overlaps the previous one).

## Actions
1. **Initialize variable** `runStart` = `utcNow()`.
2. **List rows** (Dataverse) `cr_riskrunlog`, top 1, order by `cr_startedon desc` -> `lastRun`.
   `since` = `coalesce(first(outputs('List_rows_lastRun')?['body/value'])?['cr_startedon'], addHours(utcNow(), -24))`
3. **Get tracking events** (custom connector "Visibility API", operation `GetEventsSince`)
   - `since`: `@{variables('since')}`, `status`: `in_transit`, paging on (threshold 5000).
4. **Apply to each** event: **Upsert row** `cr_scanevent` (alternate key `cr_eventid`).
   Update `cr_shipmentrisk` last scan columns: `cr_lastscanlabel`, `cr_lastscanlocation`, `cr_lastscanon`, `cr_customsstatus`.
5. **List rows** `cr_shipmentrisk` where `cr_status eq 'in_transit'` (select only the feature columns).
6. **HTTP** POST to the Azure Function `score` (see `../src/azure_function/function_app.py`), authentication Managed identity.
   - Body: `{"asOf": "@{variables('runStart')}", "shipments": @{body('List_rows_open')?['value']}}`
   - Response: `[{ "shipment_id", "score", "band", "points", "reasons": [{factor, points, text}] }]`
7. **Apply to each** result (concurrency 10):
   - **Update row** `cr_shipmentrisk`: `cr_score`, `cr_band`, `cr_points` (JSON), `cr_scoredon` = `runStart`, `cr_previousband` = old band.
   - **Delete and add** `cr_riskreason` rows for the shipment (rank 1-3, text, points).
   - **Condition** new critical: `@and(equals(items('Apply_to_each_result')?['band'], 'critical'), not(equals(outputs('Get_row')?['body/cr_band'], 'critical')))`
     - Yes: take the `card` field the function returns for critical shipments (same shape as `../teams/alert-card.json`), then
       **Post card in a chat or channel** (Teams, post as Flow bot, channel "Control tower").
       Save the returned message id to a new `cr_riskalert` row (status `open`).
8. **Add row** `cr_riskrunlog`: started, finished, events read, shipments scored, new critical count.

## Card button handling
Buttons use `Action.Submit` with `data.action`. A second flow, trigger **When someone responds to an adaptive card** (or "Post adaptive card and wait for a response" per alert), switches on `action`:
- `acknowledge`: set `cr_riskalert.cr_status = acknowledged`, `cr_acknowledgedby`, `cr_acknowledgedon`; update the card to show who acknowledged.
- `draft_customer_update`: call the Copilot Studio topic "Draft customer update" through the agent's flow action, store draft on the alert, send planner an approval.
- `escalate_to_carrier`: run "Inbound Risk - Escalate to carrier" (agent-actions.md) in preview mode and send the planner an approval.

## Error handling
- Scope "Try" around steps 3-7; "Catch" scope runs after failed or timed-out, posts a plain message to the control tower channel and writes the error to `cr_riskrunlog`.
- If the scoring call fails, scores keep their previous values; `cr_scoredon` shows they are stale and the agent quotes that time.
