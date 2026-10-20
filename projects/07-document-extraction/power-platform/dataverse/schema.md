# Dataverse schema: AP invoice intake

Status: design. Publisher prefix `ap`. Mirrors the SQLite `invoices` and `audit_log` tables in `intake/store.py` plus the master data CSVs.

## ap_vendor (Vendor)

| Column | Type | Notes |
|---|---|---|
| ap_vendorid | Primary key (GUID) | |
| ap_vendorcode | Text (20), alternate key | e.g. V001 |
| ap_name | Text (200), primary name | |
| ap_normalisedname | Text (200) | lower case, trimmed; used for name fallback |
| ap_vatid | Text (20), alternate key | e.g. NL812345671B01 |
| ap_active | Yes/No | |

## ap_purchaseorder (Purchase Order)

| Column | Type | Notes |
|---|---|---|
| ap_ponumber | Text (20), primary name, alternate key | e.g. PO-4500100 |
| ap_vendor | Lookup to ap_vendor | |
| ap_netamount | Currency | |
| ap_status | Choice: Open, Closed | |

## ap_invoice (Invoice)

| Column | Type | Notes |
|---|---|---|
| ap_name | Text, primary name | vendor + invoice number |
| ap_sourcefile | Text / URL | SharePoint link |
| ap_vendor | Lookup to ap_vendor | empty when unknown |
| ap_vendornameread | Text (200) | as printed |
| ap_vatidread | Text (20) | as printed |
| ap_invoicenumber | Text (50) | |
| ap_invoicedate | Date only | |
| ap_purchaseorder | Lookup to ap_purchaseorder | |
| ap_ponumberread | Text (20) | as printed, kept when PO not found |
| ap_currency | Text (3) | |
| ap_netamount, ap_vatamount, ap_totalamount | Currency | |
| ap_minconfidence | Decimal (0 to 1) | lowest required-field confidence |
| ap_confidencejson | Multiline text | per-field confidence from AI Builder |
| ap_status | Choice: Approved, Exception, Released, Rejected | |
| ap_reasoncodes | Text (400) | comma-separated reason codes, for views and the agent |
| ap_reasons | Multiline text | JSON array of {code, text} |
| ap_extractor | Choice: AI Builder prebuilt, AI Builder custom, Manual | |
| ap_decisioncomment | Multiline text | required for Released / Rejected |
| ap_decidedby | Lookup to User | |
| ap_decidedon | Date and time | |

Alternate key: (ap_vendor, ap_invoicenumber) supports the duplicate check; duplicates are still inserted with status Exception, so the key is not enforced as unique for Exception rows (use a separate `ap_dupkey` column filled only for Approved and Released rows if strict uniqueness is wanted).

## ap_auditevent (Audit Event)

| Column | Type | Notes |
|---|---|---|
| ap_invoice | Lookup to ap_invoice | |
| ap_action | Choice: Auto-approved, Needs review, Released, Rejected, Flow error | |
| ap_actor | Text (100) | `intake-flow`, user name, or `user (via agent)` |
| ap_comment | Multiline text | |
| createdon | System | timestamp |

Rows are create-only: security role grants Create and Read, no Write or Delete. Dataverse auditing is also enabled on `ap_invoice.ap_status`.

## Relationships

- ap_vendor 1:N ap_purchaseorder
- ap_vendor 1:N ap_invoice
- ap_purchaseorder 1:N ap_invoice
- ap_invoice 1:N ap_auditevent (cascade: restrict delete)

## Reason codes (choice set `ap_reasoncode`, used in views and topics)

EXTRACTION_INCOMPLETE, LOW_CONFIDENCE, UNKNOWN_VENDOR, MISSING_PO, PO_NOT_FOUND, PO_VENDOR_MISMATCH, AMOUNT_MISMATCH, VAT_MISMATCH, TOTAL_MISMATCH, DUPLICATE. All but LOW_CONFIDENCE exist in the Python app.
