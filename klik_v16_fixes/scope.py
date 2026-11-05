"""A seller bound to a branch sees that branch in KLiK's lists.

KLiK limits most of its lists to the seller's POS Profile or opening entry, but these read the whole
company. Each wrapper calls KLiK's own function and takes out what belongs to another branch; a user
with no branch (User.branch empty, the head office) gets KLiK's answer untouched. Stock and items are
already by the profile's warehouse, and customers are the company's, not a branch's.
"""

import frappe
from klik_pos.api import customer as klik_customer
from klik_pos.api import payment as klik_payment
from klik_pos.api import sales_invoice as klik_invoice

CAP = 500


def _bound():
	if not frappe.get_meta("User").has_field("branch") or "System Manager" in frappe.get_roles():
		return None
	return frappe.db.get_value("User", frappe.session.user, "branch") or None


def _invoices_of(names, branch):
	"""Which of these invoices are this branch's: its own, or with a line from here."""
	if not names:
		return set()
	rows = frappe.db.sql(
		"""select parent from `tabSales Invoice Item` where parent in %(n)s and warehouse = %(b)s
		union select name from `tabSales Invoice` where name in %(n)s and set_warehouse = %(b)s""",
		{"n": list(names), "b": branch},
	)
	return {row[0] for row in rows}


def _keep(result, is_mine):
	"""The same answer with only the rows is_mine accepts, wherever it keeps its list."""
	if isinstance(result, list):
		rows = [r for r in result if isinstance(r, dict) and r.get("name")]
		mine = is_mine([r["name"] for r in rows])
		return [r for r in result if not (isinstance(r, dict) and r.get("name")) or r["name"] in mine]
	if isinstance(result, dict):
		for key, value in list(result.items()):
			if isinstance(value, list):
				result[key] = _keep(value, is_mine)
				if "total_count" in result:
					result["total_count"] = len(result[key])
	return result


def _page(result, start, limit):
	"""KLiK pages before we filter, so ask it for its most and page here."""
	if isinstance(result, dict) and isinstance(result.get("data"), list):
		start, limit = int(start or 0), int(limit or 100)
		result["data"] = result["data"][start:start + limit]
		result.update({"start": start, "limit": limit})
	return result


@frappe.whitelist()
def get_outstanding_sales_invoices(limit=100, start=0, search=""):
	branch = _bound()
	if not branch:
		return klik_payment.get_outstanding_sales_invoices(limit, start, search)
	result = klik_payment.get_outstanding_sales_invoices(CAP, 0, search)
	return _page(_keep(result, lambda names: _invoices_of(names, branch)), start, limit)


@frappe.whitelist()
def get_unallocated_customer_payment_entries(limit=100, start=0, search=""):
	branch = _bound()
	if not branch:
		return klik_payment.get_unallocated_customer_payment_entries(limit, start, search)
	cost_center = frappe.db.get_value("Warehouse", branch, "branch_cost_center")

	def mine(names):
		rows = frappe.get_all("Payment Entry", filters={"name": ["in", names]}, fields=["name", "cost_center"]) if names else []
		return {r.name for r in rows if r.cost_center == cost_center}

	return _page(_keep(klik_payment.get_unallocated_customer_payment_entries(CAP, 0, search), mine), start, limit)


@frappe.whitelist()
def get_customer_invoices_for_return(customer, start_date=None, end_date=None, shipping_address=None):
	result = klik_invoice.get_customer_invoices_for_return(customer, start_date, end_date, shipping_address)
	branch = _bound()
	return _keep(result, lambda names: _invoices_of(names, branch)) if branch else result


def _replace(result, values):
	"""Put these figures wherever the answer keeps them."""
	if isinstance(result, dict):
		for key in result:
			if key in values:
				result[key] = values[key]
			else:
				_replace(result[key], values)
	return result


@frappe.whitelist()
def get_customer_statistics(customer_id):
	"""The customer's figures with this branch's invoices."""
	result = klik_customer.get_customer_statistics(customer_id)
	branch = _bound()
	if not branch:
		return result
	row = frappe.db.sql(
		"""select count(*) n, coalesce(sum(s.grand_total), 0) total, max(s.posting_date) last from `tabSales Invoice` s
		where s.customer = %(c)s and s.docstatus = 1 and s.is_return = 0 and s.status != 'Cancelled'
		and coalesce(s.custom_pos_opening_entry, '') != ''
		and (s.set_warehouse = %(b)s or exists (select 1 from `tabSales Invoice Item` i where i.parent = s.name and i.warehouse = %(b)s))""",
		{"c": customer_id, "b": branch}, as_dict=True,
	)[0]
	return _replace(result, {"total_orders": row.n, "total_spent": row.total, "last_visit": row.last})
