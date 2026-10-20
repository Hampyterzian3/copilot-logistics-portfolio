# AI Builder: invoice extraction model

Status: design. Replaces `ClaudeExtractor` / `RuleExtractor` from the Python app. Output must map 1:1 onto the `InvoiceFields` schema so the validation rules do not change.

## Option A: prebuilt invoice processing (start here)

- No training. Call **Extract information from invoices** in Power Automate with the file content.
- Returns standard fields with a confidence score each (0 to 1), plus line items.
- Field mapping to the app schema:

| App field (`InvoiceFields`) | Prebuilt output | Notes |
|---|---|---|
| `vendor_name` | Vendor name | |
| `vendor_vat_id` | Vendor tax ID | Normalise: upper case, strip spaces and dots |
| `invoice_number` | Invoice ID | Keep exactly as printed |
| `invoice_date` | Invoice date | Convert to `yyyy-MM-dd` |
| `po_number` | Purchase order | Often missed on non-standard layouts; see option B |
| `currency` | Currency code (from amount) | Default `EUR` if blank and vendor is NL |
| `net_amount` | Subtotal | |
| `vat_amount` | Total tax | |
| `total_amount` | Invoice total | |

Decision rule: run the prebuilt model on 20 to 30 real invoices per main supplier group. If `po_number`, `vendor_vat_id` or `net_amount` is wrong or below threshold on more than about 1 in 10 documents for a layout, add option B for that layout.

## Option B: custom document processing model

- Model type: **Document processing**, template-based (fixed layouts) or free-form if layouts vary within a vendor.
- Collections: one collection per layout. Minimum **5 documents per collection**; aim for 10 to 15.
- Training set: at least **5 layouts**, for example:
  1. Layout A: label-value header block, English number format (as in the synthetic set)
  2. Layout B: Dutch number format (1.234,56) and dd-mm-yyyy dates
  3. Layout C: table-style header with PO in a reference column
  4. Scanned or photographed invoices from smaller suppliers
  5. Multi-page invoices where totals are on the last page
- Fields to tag: the nine fields above. Tag `po_number` even when the label differs ("Your ref", "Order no.", "Bestelnummer").
- Hold back 20% of documents per layout for testing. Record per-field accuracy before publishing.
- Retrain when a new supplier layout reaches about 20 invoices per month, or when that layout's low-confidence rate rises.

## Confidence thresholds

| Field group | Threshold | Below threshold |
|---|---|---|
| `invoice_number`, `net_amount`, `vat_amount`, `total_amount` | 0.80 | `LOW_CONFIDENCE` exception, field highlighted for the reviewer |
| `vendor_vat_id`, `po_number` | 0.70 | `LOW_CONFIDENCE`; the deterministic vendor and PO checks still run |
| `vendor_name`, `invoice_date`, `currency` | 0.60 | Logged only; vendor is matched by VAT number first |

- Thresholds are starting points, stored as environment variables (`ap_ConfRequiredAmounts`, `ap_ConfReferences`) so they can be tuned without editing the flow.
- Confidence never approves an invoice on its own. High confidence plus all controls passing is required, as in the Python app.

## Licensing and capacity

AI Builder consumes credits per page processed. Size credits from monthly invoice pages before go-live.
