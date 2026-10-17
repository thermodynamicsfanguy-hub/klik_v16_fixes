"""Fix: a failed KLiK checkout can leave a half-submitted invoice in the books.

klik_pos.api.sales_invoice.queue_sales_invoice() (and create_and_submit_invoice(),
which calls it) wraps the whole checkout in `except Exception: return
{"success": False, ...}`. Returning normally makes Frappe commit the request,
so whatever doc.submit() had already written before the error stays: an
invoice with docstatus 1, GL and stock entries, and possibly a ZATCA
clearance. ERPNext raises its credit-limit error at the end of on_submit, so
an over-limit credit sale ends up posted and unpaid, past the limit.

Both endpoints are replaced through override_whitelisted_methods with wrappers
that call KLiK unchanged and, when its catch-all failure comes back, roll the
request back — what Frappe itself does for any request that raises. The cart
stays in the browser, so the seller can retry. KLiK's deliberate failures
(stock reservation for queued invoices, replayed checkout keys) return more
keys than the catch-all and keep their writes. Remove once KLiK rolls back
itself.
"""

import frappe
from klik_pos.api import sales_invoice as klik_sales_invoice

KLIK_ERROR_TITLE = "Submit Invoice Error"


@frappe.whitelist()
def queue_sales_invoice(data):
	return _rollback_on_failure(klik_sales_invoice.queue_sales_invoice(data))


@frappe.whitelist()
def create_and_submit_invoice(data):
	return _rollback_on_failure(klik_sales_invoice.queue_sales_invoice(data))


def _rollback_on_failure(result):
	if not (isinstance(result, dict) and result.get("success") is False and set(result) == {"success", "message"}):
		return result

	# KLiK logged the traceback inside the transaction we are about to discard.
	traceback = frappe.get_all(
		"Error Log", filters={"method": KLIK_ERROR_TITLE}, pluck="error", order_by="creation desc", limit=1
	)
	frappe.db.rollback()
	# Messages queued during the failed submit (e.g. "Sales Invoice sent to ZATCA") describe work that no longer exists.
	frappe.local.message_log = []
	frappe.log_error(
		title=f"{KLIK_ERROR_TITLE} (rolled back)",
		message=traceback[0] if traceback else result.get("message"),
	)
	return result
