# Knowledge sources

| Source | Type | Used for |
|---|---|---|
| Dataverse `cr_shipmentrisk` | Dataverse table (knowledge + flow) | Current score, band, customer, carrier, lane, area, promised date |
| Dataverse `cr_riskreason` | Dataverse table | Stored plain-word reasons and points per shipment |
| Dataverse `cr_scanevent` | Dataverse table | Scan history for "where is it" questions and escalations |
| Dataverse `cr_riskalert` | Dataverse table | Alert status (open, acknowledged, escalated), who acted and when |
| SharePoint page "Inbound risk model" | SharePoint knowledge | Explains the seven factors, weights, bands and the latest backtest so the agent can answer "how does the score work" |
| SharePoint page "Customer update guidelines" | SharePoint knowledge | Tone, wording and what may not be shared with customers |

Notes
- Generative answers are allowed only over the SharePoint pages. Shipment facts always come from the Dataverse flows in the topics, so numbers are never paraphrased.
- In this repository the content of these sources is the synthetic data in `../data/` and the model description in `../README.md`.
