# Power Automate: Invoice intake

Status: design. Cloud flow in solution `APInvoiceIntake`. Mirrors `intake/pipeline.py` and `intake/validate.py`.

## Triggers (two flows, one child flow)

- **Parent 1:** SharePoint `When a file is created in a folder`, library `AP Inbox`, folder `/Incoming`. Trigger condition: `@endsWith(toLower(triggerOutputs()?['body/{FilenameWithExtension}']), '.pdf')`
- **Parent 2:** Office 365 Outlook `When a new email arrives in a shared mailbox (V2)`, mailbox `ap-invoices@contoso.example`, `Has attachments = Yes`, `Include attachments = Yes`. Apply to each PDF attachment: save to `AP Inbox/Incoming`, which fires Parent 1. One path into the child flow keeps the logic in one place.
- **Child: `Process invoice`** (input: file identifier, file name). Concurrency on Parent 1: 5.

## Child flow actions

1. **Get file content** (SharePoint) by identifier.
2. **Extract information from invoices** (AI Builder) with the content. For layouts covered by the custom model, use **Extract information from documents** instead (see `ai-builder-model.md`); choose by vendor VAT if known from the email domain, else prebuilt first.
3. **Compose `fields`**, normalised:
   - `vatId`: `toUpper(replace(replace(coalesce(outputs('Extract')?['body/responsev2/predictionOutput/result/fields/vendorTaxId/valueText'], ''), ' ', ''), '.', ''))`
   - `invoiceDate`: `formatDateTime(<invoice date value>, 'yyyy-MM-dd')`
   - amounts as `float()`, rounded with `div(float(mul(x, 100)), 100)` after `int()` where needed.
4. **Initialize variable** `reasons` (array) = `[]`.
5. **Required fields and confidence.**
   - For each of `invoice_number, invoice_date, net_amount, vat_amount, total_amount, vendor_name`: if empty, append `{"code":"EXTRACTION_INCOMPLETE","text":"Could not read: <field>"}`.
   - If any confidence is under its threshold (env vars `ap_ConfRequiredAmounts` 0.80, `ap_ConfReferences` 0.70), append `LOW_CONFIDENCE` with the field and score.
6. **Vendor lookup** (Dataverse `List rows`, table `ap_vendor`): filter `ap_vatid eq '<vatId>'`, top 1. If none, second lookup on `ap_normalisedname eq '<lower(trim(vendor_name))>'`. If still none, append `UNKNOWN_VENDOR`: `'<vendor_name>' is not in the vendor master`.
7. **PO checks** (Dataverse `List rows`, table `ap_purchaseorder`, filter `ap_ponumber eq '<po>'`):
   - empty `po_number`: `MISSING_PO`.
   - no row: `PO_NOT_FOUND`: `<po> does not exist`.
   - row vendor not equal to matched vendor: `PO_VENDOR_MISMATCH`: `<po> belongs to vendor <id>, not <id>`.
   - `abs(div(sub(net, poNet), poNet)) > ap_AmountTolerance` (env var, 0.01): `AMOUNT_MISMATCH`: `Net x vs PO y (+z%)`.
8. **VAT and totals** (2 cent tolerance, as in `validate.py`):
   - `VAT_MISMATCH` unless `vat` is within 0.02 of `net * 0.21`, `net * 0.09` or `0`.
   - `TOTAL_MISMATCH` unless `abs(net + vat - total) <= 0.02`.
9. **Duplicate** (Dataverse `List rows` on `ap_invoice`): filter `_ap_vendor_value eq <vendorId> and ap_invoicenumber eq '<number>'`, count > 0: `DUPLICATE`.
10. **Add a new row** `ap_invoice` with all fields, confidences, `ap_status` = `Approved` if `empty(variables('reasons'))` else `Exception`, `ap_reasons` = JSON string of the array, `ap_reasoncodes` = comma-separated codes, `ap_source` = SharePoint link.
11. **Add a new row** `ap_auditevent`: action `Auto-approved` or `Needs review`, actor `intake-flow`, comment = reasons joined with `; ` or `All checks passed`.
12. **Condition: approved?**
   - **Yes:** move the file to `/Processed`; optional: call the ERP connector or write to the AP export table.
   - **No:** move the file to `/Exceptions`; **Post adaptive card in a chat or channel** (Teams, AP Exceptions channel) with vendor, invoice number, total, reason chips and buttons **Open in app** and **Ask the assistant**.
13. **Scope `Catch`** (run after: has failed, timed out): log `ap_auditevent` action `Flow error`, move the file to `/Failed`, notify the AP owner. No invoice row is left half-written because step 10 runs after all checks.

## Reviewer decision (second flow)

- Trigger: Dataverse `When a row is modified`, table `ap_invoice`, columns `ap_status`, filter `ap_status eq 'Released' or ap_status eq 'Rejected'`.
- Require `ap_decisioncomment` not empty (business rule on the form enforces this too).
- Write `ap_auditevent` with the modifying user as actor and the comment.

## Environment variables

`ap_AmountTolerance` (0.01), `ap_VatRates` ("0.21,0.09,0"), `ap_ConfRequiredAmounts` (0.80), `ap_ConfReferences` (0.70), `ap_ExceptionsChannelId`.
