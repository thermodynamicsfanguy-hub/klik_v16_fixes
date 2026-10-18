## KLiK v16 Fixes

Runtime fixes for [KLiK PoS](https://github.com/Beveren-Software-Inc/klik_pos) on Frappe / ERPNext v16. The app never edits klik_pos files. It swaps three module-level names inside klik_pos at runtime, overrides two checkout endpoints, and adds five scripts to the `/klik_pos` page (`klik_page.py`). Remove each fix once KLiK ships its own.

Tested with KLiK PoS `version-16` @ `d8dde4f484`, Frappe 16.52.0, ERPNext 16.51.1.

### What it fixes

| Fix | Problem in KLiK v16 | How |
|---|---|---|
| `catalogue.py` | The item catalogue is empty for every user except Administrator, System Manager included. `sql_builder.apply_sql_permissions()` calls `build_match_conditions()` on child tables (Item Barcode, UOM Conversion Detail, ...) without a parent, gets `PermissionError`, and the replacement `SELECT 1 WHERE 1=0` then crashes with "not all arguments converted". | Replaces `klik_pos.api.sql_builder.build_match_conditions`. A child table is allowed when the user can read any parent DocType that embeds it; everything else goes to Frappe's original function. |
| `pricing.py` | Pricing Rules (discounts, promotions) never apply. ERPNext ≥ 16.5x `apply_pricing_rule()` requires `args["doctype"]`, which KLiK doesn't pass, so every call fails into the Error Log. | Replaces `apply_pricing_rule` in `klik_pos.api.item.pricing` and `klik_pos.api.item.pricing_rules` with a wrapper that sets `doctype="Sales Invoice"` when missing. ERPNext's own checks still run. |
| `blind_close.py` | With *Hide Expected Amount* on the POS Profile, the Close Shift dialog still shows *Expected* and *Variance*. | `klik_page.py` adds `public/js/blind_close.js` to the `/klik_pos` page. The script hides both figures when `blind_close_settings()` says so: the profile option is on and the user is not System Manager / Accounts Manager. The server-side closing entry is unchanged. |
| `checkout.py` | A checkout that fails part-way through submit stays in the books. `queue_sales_invoice()` catches every exception and returns `{"success": false}`, so Frappe commits whatever `submit()` already wrote: an over-limit credit sale ends up submitted, posted and (with ZATCA) cleared, because ERPNext checks the credit limit at the end of `on_submit`. | `override_whitelisted_methods` wraps `queue_sales_invoice` and `create_and_submit_invoice`. When KLiK's catch-all failure comes back, the request is rolled back (Frappe's normal behaviour for a failed request); KLiK's own error log entry survives. KLiK's deliberate failures, which return more fields, are left alone. |
| `closing.py` | The POS Closing Entry's *Expected* is wrong per mode of payment: sales are summed by POS Profile and date, not by shift (two sellers on one profile get each other's sales; a shift past midnight loses sales after 00:00); money collected on earlier credit sales is left out; change given back is never taken off cash. | Replaces `klik_pos.api.pos_entry._calculate_payment_reconciliation` with a per-shift calculation: Sales Invoice Payment rows of invoices linked to the shift, less change on the cash mode, plus the shift's customer receipts (KLiK's own `_fetch_opening_payment_entry_data()`). The Close Shift dialog's own *Expected* (computed in the browser from invoice payments only: no opening float, change or collections) is replaced by `public/js/closing_expected.js` with `shift_expected()`, the same calculation, and *Variance* is recomputed as the amount is typed. `shift_expected()` returns nothing to users under blind close. |
| `returns.py` | A return on a credit invoice pays out cash the customer never paid: `create_partial_return()` always refunds the full return amount (the return screen pre-fills it from `paid_amount \|\| grand_total`), and since KLiK returns are POS invoices ERPNext does not credit the original, so the customer gets the cash and still owes the invoice. Full returns (`return_sales_invoice()`) keep the original's shift, and fail on cash sales where change was given (they refund the amount handed over). | `before_validate` on KLiK returns: link to the current user's open shift; if the original still has a balance, credit it (`update_outstanding_for_self = 0`); cap the cash refund at returned amount minus what is still owed, before ERPNext recalculates (otherwise `set_total_amount_to_default_mop()` rewrites the rows). `validate` zeroes the credit note's own outstanding, as ERPNext does for non-POS returns. `public/js/return_refund.js` corrects the Return Items dialog for invoices with a balance: the refund box is set to returned minus owed, KLiK's "Paid Amount" / "Write-off" become "Cash refund" / "Deducted from balance", a line shows what the customer owes and has paid (from `refund_basis()`), and the success toast states the actual cash refund. Invoices with nothing owed are left as KLiK shows them. The Multi-Invoice Return dialog gets the same per invoice, plus a "Cash to refund" total next to KLiK's Total Return Amount. KLiK returns also carry no `sales_invoice_item`, so ERPNext let the same goods be returned repeatedly: each row is now linked to the original line and a quantity beyond sold minus already returned (linked or not) is refused. The return endpoints are overridden to roll back on failure, and the multi-invoice return creates all its returns or none, naming the invoice that failed (KLiK reported success regardless). |
| `payments_refresh.js` | The Payments screen (By Invoice / By Customer / Reconcile) reloads only the current tab's list after a payment or reconciliation, so the other tabs show settled invoices as unpaid; a seller can take cash for an invoice that is already paid (the server then refuses to record it). | Reloads the page after KLiK's "Payment received" / "Payment reconciled successfully." toast, and on tab switch when the page is over a minute old. KLiK keeps the open tab across reloads. |
| `terms.py` | Credit sales are saved due today: the checkout dialog pre-fills today and KLiK ignores the customer's payment terms (ERPNext skips terms for POS invoices). | `before_validate` on KLiK credit invoices: when the due date is still the posting date, take it from the customer's (or customer group's) payment terms with ERPNext's `get_due_date()`; a date the seller picked is kept. `public/js/credit_terms.js` puts that date into the dialog with a note naming the terms. |

Fixes are installed once per process from `before_request` and `before_job`. After installing the app, restart the web and worker processes so they load its hooks.

### Checking a KLiK update

Each fix relies on KLiK internals, and a KLiK update can break one silently. `compat.py` lists those dependencies: the functions each fix replaces or wraps, the behaviour it corrects, the fields it reads, and the labels the page scripts match in KLiK's built bundle. Run it after every KLiK update:

```bash
bench --site <site> execute klik_v16_fixes.compat.check
bench --site <site> run-tests --app klik_v16_fixes --module klik_v16_fixes.tests.test_compat
```

A reported problem names the fix to re-test. A failed behaviour check can also mean KLiK fixed the bug and the patch can go. KLiK reports version `0.0.1` on every commit, so record the commit you tested against (currently `d8dde4f484`). The check covers names, signatures, fields and label text; it does not catch a change in page structure that keeps the same labels, so still open the return and close-shift dialogs once after an update.

### Not covered here

- **Cashier permissions.** ERPNext v16 lets only Sales Manager create POS Opening/Closing Entries. Give your cashier role read, write, create and submit on both (write is needed because submit goes through `save()`; an owner-only rule blocks submit in v16), read on `Item Price`, and, with `zatca_integration`, create on `Zatca Transactions`.
- **`Sales Person-pos_pin`.** KLiK's `before_install` deletes this field and nothing recreates it, so every Sales Person save fails. Add it as a Password custom field.

### Installation

```bash
bench get-app <this repository URL> --branch main
bench --site <site> install-app klik_v16_fixes
bench restart
```

The app ships plain JavaScript with no bundle. If `bench build` isn't run, link `klik_v16_fixes/public` to `sites/assets/klik_v16_fixes`.

### License

AGPL-3.0, the same as KLiK PoS. See `license.txt`.
