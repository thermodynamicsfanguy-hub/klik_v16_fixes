"""Fix: KLiK sells a whole carton at the single-unit price.

klik_pos.api.sales_invoice._add_uom_to_item() copies the cart line's unit onto
the invoice line only when it is not "Nos". For "Nos" it leaves the unit
empty, so ERPNext fills in the item's default sales unit. For an item sold by
the carton by default (sales_uom = Carton) and sold here as single pieces, the
invoice line becomes 1 Carton at the single-piece rate KLiK sends: twelve
pieces leave the shelf for the price of one.

_prepare_item_data() looks _add_uom_to_item up as a module global, so it is
replaced with one that always copies the chosen unit. Remove once KLiK fixes
it upstream.
"""

import frappe

_PATCHED_FLAG = "_klik_v16_fixes_uoms"


def add_uom_to_item(item_data, item):
	selected_uom = item.get("uom")
	if selected_uom:
		item_data["uom"] = selected_uom


def apply():
	"""before_request / before_job hook: install the fix once per process."""
	try:
		from klik_pos.api import sales_invoice
	except ImportError:
		return
	if getattr(sales_invoice, _PATCHED_FLAG, False):
		return
	sales_invoice._add_uom_to_item = add_uom_to_item
	setattr(sales_invoice, _PATCHED_FLAG, True)
