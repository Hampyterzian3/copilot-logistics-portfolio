# Flow: LogScenarioToDataverse

Agent flow called from the "Run a scenario" topic. Logs the scenario and its results so Power BI can map them.

## Trigger
**When an agent calls the flow** (Copilot Studio), inputs:
| Input | Type |
|---|---|
| FuelIndex | Number |
| Co2Price | Number |
| Handling | Number |
| MaxStops | Number |

## Actions
1. **Run a scenario** (custom connector Contoso Network Scenarios, operation RunScenario). Body:
   `{"fuel_index": @{triggerBody()?['number']}, "co2_price_t": @{triggerBody()?['number_1']}, "handling_ldm": @{triggerBody()?['number_2']}, "max_stops": @{triggerBody()?['number_3']}}`
   The flow calls the API itself so the logged rows always match the full response, including supplier modes.
2. **Add a new row** to Network Scenario:
   - Fuel index: `@{body('Run_a_scenario')?['params']?['fuel_index']}`
   - Recommended: Best mix
   - Saving %: `@{body('Run_a_scenario')?['recommendation']?['saving_vs_best_pure_pct']}`
   - Recommendation text: `@{body('Run_a_scenario')?['recommendation']?['text']}`
   - Requested by: `@{triggerOutputs()?['headers']?['x-ms-user-email']}` resolved to a user
3. **Apply to each** over `createArray('direct','milkrun','crossdock','bestmix')`:
   **Add a new row** to Scenario Design Result with `@{body('Run_a_scenario')?['designs']?[item()]?['cost_week']}` and the matching CO2, trucks, arrivals and vkm fields; Scenario lookup `cr_networkscenarios(@{outputs('Add_scenario')?['body/cr_networkscenarioid']})`.
4. **Apply to each** over `body('Run_a_scenario')?['supplier_modes']`, concurrency 20:
   **Add a new row** to Supplier Mode: name `@{item()?['supplier_id']}`, mode `@{item()?['mode']}`, hub `@{coalesce(item()?['hub_id'], '')}`.
5. **Respond to the agent**: ScenarioName = `@{outputs('Add_scenario')?['body/cr_name']}`.

## Error handling
Scope "Try" around steps 1 to 4; "Catch" scope runs after failure and returns ScenarioName = "not logged" so the chat still answers.

Sketch of the definition: `log-scenario-to-dataverse.json`.
