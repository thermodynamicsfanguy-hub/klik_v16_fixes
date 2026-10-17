"""Fix: KLiK's shift close ignores money collected on earlier credit sales.

Payments received from the Payments screen are Payment Entries linked to the
shift (custom_pos_opening_entry), and the cash goes into the same drawer. But
klik_pos.api.pos_entry._calculate_payment_reconciliation() builds each mode's
expected amount from Sales Invoice Payment rows only, so the POS Closing Entry
shows those collections as an unexplained surplus — or, under blind close,
lets them go missing unnoticed.

create_closing_entry() looks the function up as a module global at call time,
so replacing that one name is enough. The wrapper keeps KLiK's rows and adds
the shift's customer receipts per mode, using KLiK's own
_fetch_opening_payment_entry_data() (the query its shift summary already
uses). Payment Entries KLiK creates at checkout for B2B invoices carry no
shift link, so nothing is counted twice. Remove once KLiK counts them itself.
"""

import frappe
from frappe.utils import flt

_PATCHED_FLAG = "_klik_v16_fixes_closing"


def _with_collections(klik_calculate):
	def calculate_payment_reconciliation(opening_entry, data):
		from klik_pos.api.payment import _fetch_opening_payment_entry_data

		rows = klik_calculate(opening_entry, data)
		collected = {
			r.mode_of_payment: flt(r.total_amount) for r in _fetch_opening_payment_entry_data(opening_entry.name)
		}
		closing_balance = data.get("closing_balance", {})

		for row in rows:
			row["expected_amount"] = flt(row["expected_amount"]) + collected.pop(row["mode_of_payment"], 0)
			row["difference"] = flt(row["closing_amount"]) - row["expected_amount"]

		for mode, amount in collected.items():
			closing_amount = flt(closing_balance.get(mode, 0))
			rows.append(
				{
					"mode_of_payment": mode,
					"opening_amount": 0,
					"expected_amount": amount,
					"closing_amount": closing_amount,
					"difference": closing_amount - amount,
				}
			)
		return rows

	return calculate_payment_reconciliation


def apply():
	"""before_request / before_job hook: install the fix once per process."""
	try:
		from klik_pos.api import pos_entry
	except ImportError:
		return
	if getattr(pos_entry, _PATCHED_FLAG, False):
		return
	pos_entry._calculate_payment_reconciliation = _with_collections(pos_entry._calculate_payment_reconciliation)
	setattr(pos_entry, _PATCHED_FLAG, True)
