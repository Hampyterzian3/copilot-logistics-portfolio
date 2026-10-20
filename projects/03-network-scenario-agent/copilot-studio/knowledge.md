# Knowledge sources

| Source | Type | Used for |
|---|---|---|
| Contoso Network Scenarios connector (`openapi.yaml`, operation `RunScenario`) | Action / tool | All numbers: cost, CO2, trucks, per-supplier modes |
| `README.md` of this project (model assumptions section) | SharePoint file | Explaining how cost, CO2 and routes are calculated |
| Dataverse table `Network Scenario` | Dataverse knowledge | Answering "what did we run last week" questions |
| Network design glossary (direct full-load, milk-run, cross-dock, ldm, line-haul) | SharePoint page | Plain-language definitions |

Not used as knowledge: carrier tariffs, customer contracts, any real supplier list. The demo data is synthetic (`data/network.json`, seed 3).
