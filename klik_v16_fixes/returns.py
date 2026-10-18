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
  (update_outstanding_for_self = 0) and caps the cash refund at what the
  customer actually paid: returned amount minus what they still owe.

ERPNext zeroes such a credit note's own outstanding only for non-POS returns
(taxes_and_totals.calculate_outstanding_amount), so a validate hook does the
same here; otherwise it would sit at -amount with nothing posted against it.

A return on a fully paid invoice keeps KLiK's refund unchanged. Remove once
KLiK handles returns on credit invoices itself.
"""

import frappe
from frappe.utils import flt


def before_validate(doc, method=None):
	if not (doc.is_return and doc.return_against and doc.is_pos and doc.get("custom_is_created_from_klik")):
		return
	if doc.docstatus != 0:
		return

	_book_in_current_shift(doc)

	still_owed = flt(frappe.db.get_value("Sales Invoice", doc.return_against, "outstanding_amount"))
	if still_owed <= 0:
		return

	doc.calculate_taxes_and_totals()
	returned = abs(flt(doc.rounded_total) or flt(doc.grand_total))
	doc.update_outstanding_for_self = 0
	_cap_refund(doc, max(returned - still_owed, 0))


def validate(doc, method=None):
	"""Runs after the controller's validate: the credit is booked against the original invoice, not this one."""
	if doc.is_return and doc.return_against and doc.is_pos and not doc.update_outstanding_for_self:
		doc.outstanding_amount = 0


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
