"""Fix: KLiK's shift close computes the wrong expected amount per mode of payment.

klik_pos.api.pos_entry._calculate_payment_reconciliation() builds each mode's
expected amount for the POS Closing Entry, and gets three things wrong:

- It sums sales by POS Profile and posting date, not by shift. Two sellers on
  one branch profile each get the other's sales in their expected cash, and a
  shift that runs past midnight loses everything sold after 00:00.
- It leaves out money collected on earlier credit sales from the Payments
  screen. Those Payment Entries are linked to the shift
  (custom_pos_opening_entry) and the cash goes into the same drawer, so the
  close shows a surplus — or, under blind close, a shortfall nobody sees.
- It counts what the customer handed over, not what stayed in the drawer:
  change given back (Sales Invoice change_amount) is never taken off cash.

This replaces the function (create_closing_entry() looks it up as a module
global at call time) with one that sums by shift: sales and returns from the
invoices' Sales Invoice Payment rows linked to the shift, less change on the
cash mode, plus the shift's customer receipts via KLiK's own
_fetch_opening_payment_entry_data(). Payment Entries KLiK creates at checkout
for B2B invoices carry no shift link, so nothing is counted twice. Remove once
KLiK fixes it upstream.
"""

import frappe
from frappe.utils import flt

_PATCHED_FLAG = "_klik_v16_fixes_closing"


def calculate_payment_reconciliation(opening_entry, data):
	from klik_pos.api.payment import _fetch_opening_payment_entry_data

	shift = opening_entry.name
	opening = {
		r.mode_of_payment: flt(r.opening_amount)
		for r in frappe.get_all(
			"POS Opening Entry Detail", filters={"parent": shift}, fields=["mode_of_payment", "opening_amount"]
		)
	}
	expected = dict(opening)

	def add(mode, amount):
		expected[mode] = expected.get(mode, 0) + flt(amount)

	for mode, amount in frappe.db.sql(
		"""
		SELECT sip.mode_of_payment, SUM(sip.amount)
		FROM `tabSales Invoice` si
		JOIN `tabSales Invoice Payment` sip ON sip.parent = si.name
		WHERE si.custom_pos_opening_entry = %s AND si.docstatus = 1
		GROUP BY sip.mode_of_payment
		""",
		shift,
	):
		add(mode, amount)

	change = flt(
		frappe.db.sql(
			"SELECT SUM(change_amount) FROM `tabSales Invoice` WHERE custom_pos_opening_entry = %s AND docstatus = 1",
			shift,
		)[0][0]
	)
	if change:
		add(_cash_mode(expected), -change)

	for row in _fetch_opening_payment_entry_data(shift):
		add(row.mode_of_payment, row.total_amount)

	closing_balance = data.get("closing_balance", {})
	modes = list(closing_balance) + [m for m in expected if m not in closing_balance]
	rows = []
	for mode in modes:
		closing_amount = flt(closing_balance.get(mode, 0))
		rows.append(
			{
				"mode_of_payment": mode,
				"opening_amount": opening.get(mode, 0),
				"expected_amount": expected.get(mode, 0),
				"closing_amount": closing_amount,
				"difference": closing_amount - expected.get(mode, 0),
			}
		)
	return rows


def _cash_mode(modes):
	cash = frappe.get_all("Mode of Payment", filters={"type": "Cash", "name": ["in", list(modes) or [""]]}, pluck="name")
	return cash[0] if cash else "Cash"


def apply():
	"""before_request / before_job hook: install the fix once per process."""
	try:
		from klik_pos.api import pos_entry
	except ImportError:
		return
	if getattr(pos_entry, _PATCHED_FLAG, False):
		return
	pos_entry._calculate_payment_reconciliation = calculate_payment_reconciliation
	setattr(pos_entry, _PATCHED_FLAG, True)
