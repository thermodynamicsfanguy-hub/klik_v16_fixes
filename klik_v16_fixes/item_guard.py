"""KLiK's serial-number lookup for signed-in users only.

klik_pos whitelists ``get_serial_nos_for_item`` with ``allow_guest=True``: anyone
on the internet could list a shop's serial numbers, warehouses included, by item
code. frappe checks the overriding function's own whitelist, so this wrapper
(no allow_guest) refuses a guest before KLiK's code runs; the till always calls it
signed in.
"""

import frappe


@frappe.whitelist()
def get_serial_nos_for_item(item_code: str):
	from klik_pos.api.item.item_details import get_serial_nos_for_item as klik

	return klik(item_code)
