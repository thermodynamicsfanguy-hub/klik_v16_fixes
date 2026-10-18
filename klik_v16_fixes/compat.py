"""Does the installed KLiK still have what this app's fixes rely on?

Every fix here leans on KLiK internals: it replaces a module-level name,
wraps an endpoint, reads a custom field, assumes a behaviour it corrects, or
(page scripts) matches KLiK's hard-coded English labels in the built bundle.
When a KLiK update renames or reshapes one of those, the fix usually stops
working silently — a patch replaces a name nobody calls any more, a script
finds nothing and fails open. This lists each dependency and reports every
one that no longer holds.

Run it after every KLiK update (the storelab rebuild script does):

    bench --site <site> execute klik_v16_fixes.compat.check

A failure means: re-test the fix named next to the problem. A failed
"behaviour" check can also mean KLiK fixed the bug itself and the patch can
go.
"""

import glob
import inspect
import os

import frappe

# (module, name, expected leading parameters or None, fix that depends on it)
FUNCTIONS = [
	("klik_pos.api.sql_builder", "build_match_conditions", None, "catalogue.py"),
	("klik_pos.api.sql_builder", "apply_sql_permissions", None, "catalogue.py"),
	("klik_pos.api.item.pricing", "apply_pricing_rule", None, "pricing.py"),
	("klik_pos.api.item.pricing_rules", "apply_pricing_rule", None, "pricing.py"),
	("klik_pos.api.pos_entry", "_calculate_payment_reconciliation", ("opening_entry", "data"), "closing.py"),
	("klik_pos.api.pos_entry", "create_closing_entry", (), "closing.py"),
	("klik_pos.api.payment", "_fetch_opening_payment_entry_data", ("opening_entry_name",), "closing.py"),
	("klik_pos.api.sales_invoice", "queue_sales_invoice", ("data",), "checkout.py"),
	("klik_pos.api.sales_invoice", "create_and_submit_invoice", ("data",), "checkout.py"),
	("klik_pos.api.sales_invoice", "get_current_pos_opening_entry", (), "returns.py"),
	("klik_pos.api.sales_invoice", "create_partial_return", ("invoice_name", "return_items"), "returns.py"),
	("klik_pos.api.sales_invoice", "return_sales_invoice", ("invoice_name",), "returns.py"),
	("klik_pos.api.pos_profile", "get_pos_details", None, "blind_close.py"),
	(
		"erpnext.controllers.taxes_and_totals",
		"calculate_taxes_and_totals.set_total_amount_to_default_mop",
		None,
		"returns.py (refund capped before this rewrites it)",
	),
]

# Behaviour a fix corrects: (module, function, text the module's source must contain, fix).
BEHAVIOUR = [
	(
		"klik_pos.api.sales_invoice",
		"queue_sales_invoice",
		'return {"success": False, "message": str(e)}',
		"checkout.py (catch-all failure returned without rollback)",
	),
	(
		"klik_pos.api.sales_invoice",
		"create_partial_return",
		'"amount": -abs(final_return_amount)',
		"returns.py (cash refund of the full return amount)",
	),
	(
		"klik_pos.api.pos_entry",
		"_calculate_payment_reconciliation",
		"WHERE si.pos_profile = %s",
		"closing.py (expected summed by profile and date, not shift)",
	),
]

FIELDS = [
	("Sales Invoice", "custom_is_created_from_klik", "returns.py"),
	("Sales Invoice", "custom_pos_opening_entry", "closing.py, returns.py"),
	("Sales Invoice", "update_outstanding_for_self", "returns.py"),
	("Payment Entry", "custom_pos_opening_entry", "closing.py"),
	("POS Profile", "custom_hide_expected_amount", "blind_close.py"),
]

# Text the page scripts match, as it appears in KLiK's minified bundle.
PAGE_TEXT = {
	"blind_close.js": ['"Expected"', '"Variance"'],
	"return_refund.js": [
		"Return Items",
		"Multi-Invoice Return",
		"Total Return Amount:",
		'"Total Return Amount"',
		"Paid Amount:",
		"Write-off:",
		"Invoice:",
		"Return created successfully (",
		'children:"Amount"',
		'step:"0.01"',
		"Toastify__toast-body",
	],
	"payments_refresh.js": [
		"Payment received: ",
		"Payment reconciled successfully.",
		'"By Invoice"',
		'"By Customer"',
		'"Reconcile"',
		"klik_pos_payment_entries_active_tab",
	],
}

BUNDLE_GLOB = ("klik_pos", "public", "klik_spa", "assets", "index-*.js")


def _resolve(module, name):
	obj = frappe.get_module(module)
	for part in name.split("."):
		obj = getattr(obj, part)
	return obj


def _module_source(module):
	# The file on disk, not the live objects: this app's patches replace some of them at runtime.
	return inspect.getsource(frappe.get_module(module))


def klik_bundle_text():
	app_dir = frappe.get_app_path(*BUNDLE_GLOB[:1])
	files = glob.glob(os.path.join(app_dir, *BUNDLE_GLOB[1:]))
	return "".join(open(f, encoding="utf-8").read() for f in sorted(files)), files


def problems(bundle_text=None):
	"""Every dependency that no longer holds, as readable lines (empty = all good)."""
	found = []

	for module, name, params, fix in FUNCTIONS:
		try:
			fn = _resolve(module, name)
			present = name.split(".")[-1] in _module_source(module)
		except (ImportError, AttributeError, OSError):
			fn, present = None, False
		if fn is None or not present:
			found.append(f"{fix}: {module}.{name} no longer exists")
			continue
		if params is None or (getattr(fn, "__module__", "") or "").startswith("klik_v16_fixes"):
			continue  # nothing to compare, or already replaced by this app (same parameters by design)
		actual = tuple(inspect.signature(inspect.unwrap(fn)).parameters)[: len(params)]
		if actual != tuple(params):
			found.append(f"{fix}: {module}.{name} parameters changed: expected {params}, now {actual}")

	for module, name, text, fix in BEHAVIOUR:
		try:
			source = _module_source(module)
		except (ImportError, OSError, TypeError):
			found.append(f"{fix}: cannot read {module}")
			continue
		if text not in source:
			found.append(f"{fix}: {module}.{name} no longer contains {text!r} — re-test, KLiK may have changed or fixed it")

	for doctype, fieldname, fix in FIELDS:
		if not frappe.get_meta(doctype).has_field(fieldname):
			found.append(f"{fix}: field {doctype}.{fieldname} is gone")

	if bundle_text is None:
		bundle_text, files = klik_bundle_text()
		if not files:
			found.append("page scripts: KLiK bundle not found at " + "/".join(BUNDLE_GLOB))
			return found
	for script, needles in PAGE_TEXT.items():
		for needle in needles:
			if needle not in bundle_text:
				found.append(f"{script}: KLiK's page no longer contains {needle!r}")

	return found


def check():
	"""bench execute entry point: print the result, raise if anything broke."""
	found = problems()
	try:
		version = frappe.get_attr("klik_pos.__version__")
	except Exception:
		version = "unknown"
	if found:
		print(f"klik_v16_fixes compat: {len(found)} problem(s) with klik_pos {version}:")
		for line in found:
			print("  - " + line)
		raise frappe.ValidationError("klik_v16_fixes no longer matches the installed KLiK; see the list above")
	checked = len(FUNCTIONS) + len(BEHAVIOUR) + len(FIELDS) + sum(len(v) for v in PAGE_TEXT.values())
	print(f"klik_v16_fixes compat: OK ({checked} checks) with klik_pos {version}")
