"""Fix: KLiK credit sales ignore the customer's payment terms.

KLiK's checkout dialog pre-fills the credit sale's due date with today, and
the invoice is saved due today even when the customer (or their customer
group) has payment terms such as 30 days. ERPNext would normally derive the
due date from the terms, but KLiK sends an explicit date, and for POS invoices
ERPNext skips payment terms altogether (set_payment_schedule).

A before_validate hook on KLiK's credit invoices: when the due date is still
the posting date (KLiK's default) and the customer has payment terms, the due
date is taken from those terms with ERPNext's own get_due_date(). A date the
seller picked deliberately is kept. public/js/credit_terms.js puts the same
date into the dialog, from default_due_date(), so the seller sees what will be
saved. Remove once KLiK applies payment terms itself.
"""

import frappe
from erpnext.accounts.party import get_due_date, get_payment_terms_template
from frappe.utils import flt, getdate


def before_validate(doc, method=None):
	if not doc.get("custom_is_created_from_klik") or doc.is_return or doc.docstatus != 0:
		return
	if flt(doc.outstanding_amount) <= 0:
		return  # paid at the till: not a credit sale
	if doc.due_date and getdate(doc.due_date) != getdate(doc.posting_date):
		return  # the seller chose a date
	due = _terms_due_date(doc.customer, doc.company, doc.posting_date)
	if due:
		doc.due_date = due


def _terms_due_date(customer, company, posting_date):
	if not get_payment_terms_template(customer, "Customer", company):
		return None
	due = get_due_date(posting_date, "Customer", customer, company)
	return due if due and getdate(due) > getdate(posting_date) else None


@frappe.whitelist()
def default_due_date(customer, company=None):
	"""The due date a credit sale to this customer gets today, or None without payment terms."""
	frappe.has_permission("Customer", "read", customer, throw=True)
	company = company or frappe.defaults.get_user_default("Company")
	due = _terms_due_date(customer, company, frappe.utils.today())
	return {"due_date": str(due) if due else None, "terms": get_payment_terms_template(customer, "Customer", company)}
