## KLiK v16 Fixes

Runtime fixes for [KLiK PoS](https://github.com/Beveren-Software-Inc/klik_pos) on Frappe / ERPNext v16. The app never edits klik_pos files. It swaps three module-level names inside klik_pos at runtime, overrides two checkout endpoints, and adds one script to the `/klik_pos` page. Remove each fix once KLiK ships its own.

Tested with KLiK PoS `version-16` @ `d8dde4f484`, Frappe 16.52.0, ERPNext 16.51.1.

### What it fixes

| Fix | Problem in KLiK v16 | How |
|---|---|---|
| `catalogue.py` | The item catalogue is empty for every user except Administrator, System Manager included. `sql_builder.apply_sql_permissions()` calls `build_match_conditions()` on child tables (Item Barcode, UOM Conversion Detail, ...) without a parent, gets `PermissionError`, and the replacement `SELECT 1 WHERE 1=0` then crashes with "not all arguments converted". | Replaces `klik_pos.api.sql_builder.build_match_conditions`. A child table is allowed when the user can read any parent DocType that embeds it; everything else goes to Frappe's original function. |
| `pricing.py` | Pricing Rules (discounts, promotions) never apply. ERPNext ≥ 16.5x `apply_pricing_rule()` requires `args["doctype"]`, which KLiK doesn't pass, so every call fails into the Error Log. | Replaces `apply_pricing_rule` in `klik_pos.api.item.pricing` and `klik_pos.api.item.pricing_rules` with a wrapper that sets `doctype="Sales Invoice"` when missing. ERPNext's own checks still run. |
| `blind_close.py` | With *Hide Expected Amount* on the POS Profile, the Close Shift dialog still shows *Expected* and *Variance*. | An `after_request` hook adds `public/js/blind_close.js` to the `/klik_pos` page. The script hides both figures when `blind_close_settings()` says so: the profile option is on and the user is not System Manager / Accounts Manager. The server-side closing entry is unchanged. |
| `checkout.py` | A checkout that fails part-way through submit stays in the books. `queue_sales_invoice()` catches every exception and returns `{"success": false}`, so Frappe commits whatever `submit()` already wrote: an over-limit credit sale ends up submitted, posted and (with ZATCA) cleared, because ERPNext checks the credit limit at the end of `on_submit`. | `override_whitelisted_methods` wraps `queue_sales_invoice` and `create_and_submit_invoice`. When KLiK's catch-all failure comes back, the request is rolled back (Frappe's normal behaviour for a failed request); KLiK's own error log entry survives. KLiK's deliberate failures, which return more fields, are left alone. |
| `closing.py` | Money collected on earlier credit sales (Payments screen) is linked to the shift but left out of the closing entry's *Expected*, so the drawer shows a surplus — or, with blind close, a shortfall nobody sees. | Replaces `klik_pos.api.pos_entry._calculate_payment_reconciliation` with a wrapper that adds the shift's customer receipts per mode of payment, using KLiK's own `_fetch_opening_payment_entry_data()`. Only the saved POS Closing Entry changes; the *Expected* figure in the close dialog is computed in the browser and still excludes them. |

Fixes are installed once per process from `before_request` and `before_job`. After installing the app, restart the web and worker processes so they load its hooks.

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
