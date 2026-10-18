"""Fix: a KLiK return on a credit invoice pays the customer cash they never paid.

create_partial_return() always books a cash refund for the full returned
amount, and the return screen pre-fills it from `paid_amount || grand_total`,
so an unpaid credit invoice shows "Customer Paid" and refunds everything. The
return is also a POS invoice, and ERPNext only credits the original invoice
for non-POS returns, so the credit note keeps its own balance: the customer
gets the cash *and* still owes the original invoice in full.
return_sales_invoice() (full return) also copies the original invoice's shift,
so its refund lands in a shift that may already be closed.

A before_validate hook on KLiK's returns:
- links the return to the current user's open shift;
- when the original invoice still has a balance, credits that invoice
  (update_outstanding_for_self = 0);
- caps the cash refund at the returned amount minus what is still owed. This
  also fixes return_sales_invoice() on a cash sale where change was given: it
  copies the amount handed over (200 for a 140 sale) as the refund, which
  ERPNext rejects, so the return could not be made at all. The cap only ever
  lowers KLiK's refund.

ERPNext zeroes such a credit note's own outstanding only for non-POS returns
(taxes_and_totals.calculate_outstanding_amount), so a validate hook does the
same here; otherwise it would sit at -amount with nothing posted against it.

The return screen still pre-fills KLiK's figures ("Customer Paid" = the whole
invoice, refund = everything); public/js/return_refund.js corrects them from
refund_basis() so the seller sees the refund that will actually be booked.

KLiK's returns also carry no link to the original invoice line
(sales_invoice_item). ERPNext counts already-returned quantity per line, so
without the link every return is checked against the full quantity sold and
the same goods can be returned again and again (KLiK's screen limits it, but
two sellers, a stale screen or a direct call do not). before_validate links
each row to the original line and refuses a quantity beyond what was sold
minus everything already returned against the invoice, linked or not.

KLiK's return endpoints also swallow errors without rolling back (like
checkout, see checkout.py), and create_multi_invoice_return() reports success
even when some invoices failed. The endpoints are overridden below: a failed
return is rolled back, and a multi-invoice return creates all of its returns
or none, naming the invoice that failed.

Remove once KLiK handles returns on credit invoices itself.
"""

import json

import frappe
from frappe.utils import flt
from klik_pos.api import sales_invoice as klik_sales_invoice

from klik_v16_fixes.checkout import rollback_on_failure


def before_validate(doc, method=None):
	if not (doc.is_return and doc.return_against and doc.is_pos and doc.get("custom_is_created_from_klik")):
		return
	if doc.docstatus != 0:
		return

	_book_in_current_shift(doc)
	_link_and_limit_quantities(doc)

	still_owed = max(flt(frappe.db.get_value("Sales Invoice", doc.return_against, "outstanding_amount")), 0)
	if still_owed:
		doc.update_outstanding_for_self = 0

	# Cap before ERPNext recalculates: when a POS return's refund exceeds the
	# return, taxes_and_totals.set_total_amount_to_default_mop() replaces the
	# payment rows with the difference. KLiK has already set the totals here
	# (partial returns recalculate, full returns copy the original's).
	returned = abs(flt(doc.rounded_total) or flt(doc.grand_total))
	_cap_refund(doc, returned - still_owed)


def validate(doc, method=None):
	"""Runs after the controller's validate: the credit is booked against the original invoice, not this one."""
	if doc.is_return and doc.return_against and doc.is_pos and not doc.update_outstanding_for_self:
		doc.outstanding_amount = 0


def _link_and_limit_quantities(doc):
	original = frappe.get_all(
		"Sales Invoice Item",
		filters={"parent": doc.return_against},
		fields=["name", "item_code", "stock_qty"],
		order_by="idx",
	)
	returned = dict(
		frappe.db.sql(
			"""
			SELECT child.item_code, SUM(ABS(child.stock_qty))
			FROM `tabSales Invoice Item` child
			JOIN `tabSales Invoice` ret ON ret.name = child.parent
			WHERE ret.return_against = %s AND ret.is_return = 1 AND ret.docstatus = 1 AND ret.name != %s
			GROUP BY child.item_code
			""",
			(doc.return_against, doc.name or ""),
		)
	)
	sold = {}
	for row in original:
		sold[row.item_code] = sold.get(row.item_code, 0) + flt(row.stock_qty)

	asked = {}
	for row in doc.items:
		if not row.get("sales_invoice_item"):
			match = next((o.name for o in original if o.item_code == row.item_code), None)
			if match:
				row.sales_invoice_item = match
		asked[row.item_code] = asked.get(row.item_code, 0) + abs(flt(row.qty)) * flt(row.conversion_factor or 1)

	for item_code, qty in asked.items():
		left = sold.get(item_code, 0) - flt(returned.get(item_code))
		if qty > left + 0.0001:
			frappe.throw(
				f"{item_code}: sold {sold.get(item_code, 0):g}, already returned {flt(returned.get(item_code)):g} "
				f"on {doc.return_against} — cannot return {qty:g} more (quantities in stock units)."
			)


def _book_in_current_shift(doc):
	from klik_pos.api.sales_invoice import get_current_pos_opening_entry

	shift = get_current_pos_opening_entry()
	if shift:
		doc.custom_pos_opening_entry = shift


def _cap_refund(doc, refundable):
	left = refundable
	for row in doc.payments:
		amount = min(abs(flt(row.amount)), left)
		row.amount = -amount
		row.base_amount = -amount * flt(doc.conversion_rate or 1)
		left -= amount


@frappe.whitelist()
def refund_basis(invoice):
	"""What the customer still owes and has paid on an invoice, for the return screen."""
	frappe.has_permission("Sales Invoice", "read", invoice, throw=True)
	grand_total, owed = frappe.db.get_value("Sales Invoice", invoice, ["grand_total", "outstanding_amount"])
	owed = max(flt(owed), 0)
	return {"owed": owed, "paid": flt(grand_total) - owed}


@frappe.whitelist()
def create_partial_return(invoice_name, return_items, payment_method=None, return_amount=None, expected_return_amount=None):
	return rollback_on_failure(
		klik_sales_invoice.create_partial_return(
			invoice_name, return_items, payment_method, return_amount, expected_return_amount
		)
	)


@frappe.whitelist()
def return_sales_invoice(invoice_name):
	return rollback_on_failure(klik_sales_invoice.return_sales_invoice(invoice_name))


@frappe.whitelist()
def create_multi_invoice_return(return_data):
	"""KLiK's multi-invoice return, all or nothing."""
	klik_sales_invoice._ensure_return_allowed()
	if isinstance(return_data, str):
		return_data = json.loads(return_data)

	created = []
	for invoice_return in return_data.get("invoice_returns", []):
		if not invoice_return.get("return_items"):
			continue
		invoice = invoice_return.get("invoice_name")
		result = klik_sales_invoice.create_partial_return(
			invoice,
			invoice_return.get("return_items"),
			payment_method=invoice_return.get("payment_method"),
			return_amount=invoice_return.get("return_amount"),
		)
		if not result.get("success"):
			frappe.db.rollback()
			frappe.local.message_log = []
			return {
				"success": False,
				"message": f"{invoice}: {result.get('message')} — no returns were created.",
			}
		created.append(result.get("return_invoice"))

	return {
		"success": True,
		"created_returns": created,
		"message": f"Created {len(created)} return invoices successfully",
	}
