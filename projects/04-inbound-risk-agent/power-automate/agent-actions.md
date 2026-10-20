# Flows called by the Copilot Studio agent

All three use the trigger **When an agent calls the flow** (Copilot Studio) and end with **Respond to the agent**.

## Inbound Risk - Get at-risk shipments
- Inputs: `customerName` (text), `minimumBand` (text: `watch`, `at_risk`, `critical`).
- **List rows** `cr_customer` where `contains(cr_name, customerName)`, top 1 -> `matchedCustomer`.
- **List rows** `cr_shipmentrisk` where `_cr_customer_value eq <id> and cr_status eq 'in_transit'`, order by `cr_score desc`.
- **Filter array** bands at or above `minimumBand` (rank: critical 3, at_risk 2, watch 1).
- **Select** each row to a line: `concat('- ', item()?['cr_shipmentid'], ' (', item()?['cr_band'], ', ', item()?['cr_score'], '): ', item()?['cr_topreason'])`, take first 10.
- Outputs: `matchedCustomer`, `inTransit` (`length(...)`), `critical`, `atRisk`, `watch` (counts), `shipmentLines` (`join(body('Select'), decodeUriComponent('%0A'))`), `scoredAt` (`formatDateTime(max cr_scoredon, 'HH:mm')`).

## Inbound Risk - Get shipment reasons
- Inputs: `shipmentId` (text), `customerSafe` (boolean, default false).
- **Get row** `cr_shipmentrisk` by alternate key `cr_shipmentid`; **List rows** `cr_riskreason` for it, order by `cr_rank`.
- `reasonLines`: `- <text> (+<points> points)` per reason.
- When `customerSafe` is true, keep only reasons with factor in `dwell`, `customs`, `slack`, `calendar`, and map them to customer wording (same mapping as the demo: missing scan, customs checks, time left versus transit time, weekend or holiday). Lane, area and carrier statistics are never returned in this mode.
- Outputs: `found`, `score`, `bandLabel`, `reasonLines`, `lastScan`, `promised`, `customer`, `poRef`, `pieces`, `carrier`, `isOverdue` (`less(cr_daystopromise, 0)`), `customerCauses`, `scoredAt`.

## Inbound Risk - Escalate to carrier
- Inputs: `shipmentId`, `mode` (`preview` or `send`).
- Look up carrier contact in `cr_carrier.cr_opsemail`.
- Subject: `concat('Escalation ', shipmentId, ': please confirm location and ETA within 2 hours')`.
- Body lists band, score, last scan and hours since scan (`div(sub(ticks(utcNow()), ticks(cr_lastscanon)), 36000000000)`), promised date, and three questions (location, next scan and revised ETA, any damage, loss or customs issue).
- `send` mode: **Send an email (V2)** from the control tower shared mailbox, set `cr_riskalert.cr_status = escalated`, `cr_escalatedon = utcNow()`, `dueBy = addHours(utcNow(), 2)`.
- Outputs: `found`, `carrier`, `carrierEmail`, `subject`, `body`, `dueBy`.
