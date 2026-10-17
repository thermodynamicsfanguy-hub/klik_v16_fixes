"""Runtime fix: KLiK PoS v16 hides the catalogue from every non-Administrator.

klik_pos.api.sql_builder.apply_sql_permissions() calls Frappe's
build_match_conditions(doctype) on the first table of each raw SQL query.
For a child table (Item Barcode, UOM Conversion Detail, Sales Invoice Item,
...) Frappe v16 raises PermissionError when no parent doctype is given — even
for System Manager — and KLiK then swaps the query for "SELECT 1 WHERE 1=0"
while still passing the original parameters, so MySQLdb fails with
"not all arguments converted" and KLiK reports
"Something went wrong while fetching item data". Only Administrator, who
bypasses permission checks, ever sees items.

This app never edits klik_pos. sql_builder looks build_match_conditions up as
a module global at call time, so replacing that one name covers all of
KLiK's ~80 call sites. For a child table, read access to any parent doctype
that embeds it grants access with no extra conditions — Frappe's own rule
for child rows. Every other doctype goes to Frappe's original function
unchanged. Remove this module once KLiK fixes it upstream.
"""

import frappe
from frappe.desk.reportview import build_match_conditions as frappe_build_match_conditions

_PATCHED_FLAG = "_klik_v16_fixes_catalogue"


def _parents_of(child_doctype):
	cache = frappe.local.__dict__.setdefault("klik_v16_fixes_child_parents", {})
	if child_doctype not in cache:
		filters = {"options": child_doctype, "fieldtype": ["in", ["Table", "Table MultiSelect"]]}
		parents = set(frappe.get_all("DocField", filters=filters, pluck="parent"))
		parents |= set(frappe.get_all("Custom Field", filters=filters, pluck="dt"))
		cache[child_doctype] = parents
	return cache[child_doctype]


def build_match_conditions(doctype, user=None, as_condition=True):
	if frappe.get_meta(doctype).istable:
		if any(frappe.has_permission(parent, "read", user=user) for parent in _parents_of(doctype)):
			return "" if as_condition else []
		raise frappe.PermissionError(doctype)
	return frappe_build_match_conditions(doctype, user=user, as_condition=as_condition)


def apply():
	"""before_request / before_job hook: install the fix once per process."""
	try:
		from klik_pos.api import sql_builder
	except ImportError:
		return
	if getattr(sql_builder, _PATCHED_FLAG, False):
		return
	sql_builder.build_match_conditions = build_match_conditions
	setattr(sql_builder, _PATCHED_FLAG, True)
