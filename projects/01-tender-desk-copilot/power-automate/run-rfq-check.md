# Flow: Tender Desk - Run RFQ check

Automated cloud flow. Runs the RFQ checker when a solution designer creates a new RFQ folder, stores the result and tells the team. Also callable from Copilot Studio (topic "Check new RFQ") through a second trigger in a child flow with the same actions.

Definition sketch: `run-rfq-check.json`.

## Trigger
**SharePoint: When a file is created or modified (properties only)**
- Site: `https://contoso.sharepoint.com/sites/TenderDesk`
- Library: `RFQ Library`
- Trigger condition (only new folders):
  `@and(equals(triggerBody()?['{IsFolder}'], true), equals(triggerBody()?['{VersionNumber}'], '1.0'))`

## Actions
1. **Delay until files arrive**: `Do until` both files exist (max 12 loops, 5 minute delay).
   - **Get files (properties only)** with filter `FileDirRef eq '@{triggerBody()?['{FullPath}']}'`.
   - Exit condition: `@greaterOrEquals(length(filter(body('Get_files')?['value'], item()?['{FilenameWithExtension}'] in createArray('lanes.csv','requirements.md'))), 2)`
2. **Get file content** `lanes.csv` and **Get file content** `requirements.md` (path `@{triggerBody()?['{FullPath}']}/lanes.csv`).
3. **CheckRfq** (custom connector "Tender Desk Checker", backed by the Azure Function in `src/function_app.py`):
   - `lanes_csv`: `@{base64ToString(body('Get_lanes')?['$content'])}`
   - `requirements_md`: `@{base64ToString(body('Get_requirements')?['$content'])}`
   - `meta.id`: `@{triggerBody()?['{Name}']}`
4. **Dataverse: Add a new row** to `Tender` (title, folder, lane count, readiness %, gap counts, countries `@{join(body('CheckRfq')?['scope']?['countries'], ', ')}`).
5. **Apply to each** `@{body('CheckRfq')?['lanes']}`: add row to `RFQ Lane` (lookup to Tender, mode suggested, flags `@{join(items('Apply_to_each_lane')?['flags'], ',')}`).
6. **Apply to each** `@{body('CheckRfq')?['gaps']}`: add row to `RFQ Gap` (rule id, severity, lane id, message, status = Open).
7. **Apply to each** theme in `questions`, then each question: add row to `Clarification Question` (theme, text, status = Draft).
8. **SharePoint: Create file** `rfq-summary.md` in the RFQ folder with `@{body('CheckRfq')?['markdown']}`. This is the file Microsoft 365 Copilot in Word and PowerPoint is pointed at.
9. **Teams: Post adaptive card in a chat or channel** (team `Tender Desk`, channel `New RFQs`):
   - Title: `RFQ checked: @{triggerBody()?['{Name}']}`
   - Facts: lanes, readiness `@{body('CheckRfq')?['summary']?['readiness_pct']}%`, high / medium / low gaps.
   - Button: "Open in Tender Desk agent" (deep link to the Copilot Studio agent in Teams) and "Open folder".
10. **Respond to Copilot** (child flow only): return `tenderId`, `lanes`, `gapsHigh`, `gapsMedium`, `gapsLow`, `readinessPct`, `topGaps` (first five high gaps joined with line breaks).

## Error handling
- Scope `Try` around steps 3 to 9; `Catch` scope runs after failure or timeout and posts "RFQ check failed, see run history" to the channel with the flow run link `@{concat('https://make.powerautomate.com/environments/', workflow()?['tags']?['environmentName'], '/flows/', workflow()?['name'], '/runs/', workflow()?['run']?['name'])}`.
- Custom connector timeout 120 seconds; retry policy exponential, 3 attempts.

## Second flow: Tender Desk - Create clarification draft
Instant flow called by the topic "Draft clarification questions".
1. Inputs: `rfqFolder`.
2. **Dataverse: List rows** `Clarification Question` filtered by tender, ordered by theme.
3. **Word Online (Business): Populate a Microsoft Word template** (`Solution templates/Clarification letter.docx`) with shipper, title, due date and a repeating section of questions.
4. **Create file** `Clarification letter (draft).docx` in the RFQ folder.
5. **Respond to Copilot**: `questionCount`, `themes`, `draftUrl`.
