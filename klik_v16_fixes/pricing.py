"""Runtime fix: KLiK PoS never applies pricing rules on ERPNext >= 16.5x.

ERPNext added validate_pricing_context() to apply_pricing_rule(): the args
must name the transaction doctype (one of PRICING_TRANSACTION_DOCTYPES),
otherwise it throws PermissionError("Invalid doctype") — for every user,
Administrator included. KLiK's cart pricing (klik_pos.api.item.pricing and
klik_pos.api.item.pricing_rules) builds the args without "doctype", catches
the error into the Error Log ("Pricing Rule Error") and carries on, so
discounts and promotions silently never apply at the till.

This app never edits klik_pos. Both modules import apply_pricing_rule as a
module global, so we swap that name for a wrapper that fills in
doctype="Sales Invoice" (what KLiK submits) when it is missing. ERPNext's own
checks — permission on Sales Invoice, the customer, the price list — still
run unchanged. Remove once KLiK passes the doctype itself.
"""

import json

import frappe
from erpnext.accounts.doctype.pricing_rule.pricing_rule import apply_pricing_rule as erpnext_apply_pricing_rule

KLIK_MODULES = ("klik_pos.api.item.pricing", "klik_pos.api.item.pricing_rules")
POS_TRANSACTION = "Sales Invoice"
_PATCHED_FLAG = "_klik_v16_fixes_pricing"


def apply_pricing_rule(args, doc=None):
	if isinstance(args, str):
		args = json.loads(args)
	args = frappe._dict(args)
	if not args.get("doctype"):
		args.doctype = POS_TRANSACTION
	return erpnext_apply_pricing_rule(args, doc=doc)


def apply():
	"""before_request / before_job hook: install the fix once per process."""
	for name in KLIK_MODULES:
		try:
			module = frappe.get_module(name)
		except ImportError:
			continue
		if getattr(module, _PATCHED_FLAG, False):
			continue
		module.apply_pricing_rule = apply_pricing_rule
		setattr(module, _PATCHED_FLAG, True)
