# Knowledge sources

| Source | Type | Used for | Notes |
|---|---|---|---|
| Power BI semantic model "Contoso Account KPIs" | Data, via Power Automate flows (DAX `executeQueries`) | All numbers: KPIs, WoW, baseline, z, materiality, margin bridge | Certified; RLS applies to the flow's identity. The agent never queries raw tables. |
| Dataverse table `kpi_weeklyvariance` | Data, via flow | Flagged variances per week, with fact ids | Written by the Monday flow; read-only for the agent |
| Dataverse table `kpi_briefdraft` | Data, via flow | Generated brief, slide outline and Teams text with source refs, approval status | One row per week |
| SharePoint: `Commercial Analytics/KPI definitions.docx` | Knowledge (SharePoint) | Definitions of each KPI, thresholds and how materiality is scored | Owner: analytics lead, reviewed quarterly |
| SharePoint: `Commercial Analytics/Brief style guide.docx` | Knowledge (SharePoint) | Tone, structure and wording rules for leadership briefs | British English, no em dashes |
| `powerbi/semantic-model.md` (this repo) | Reference | Table, measure and threshold design | Mirrors the deployed model |

Not used as knowledge: public web, email, chat history, customer contracts. General knowledge is switched off in the agent settings so answers come only from the flows and the two SharePoint documents.
