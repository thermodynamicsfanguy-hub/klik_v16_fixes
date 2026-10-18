"""Blind shift close for KLiK PoS, without editing klik_pos.

KLiK's POS Profile option "Hide Expected Amount" (custom_hide_expected_amount)
hides the payment summary on the closing page, but its Close Shift dialog
still prints "Expected" and "Variance" — and the variance alone gives the
expected amount away. The cashier should count without knowing the target.

public/js/blind_close.js is added to KLiK's page by klik_page.py, and asks
blind_close_settings() whether to hide the two figures.

Only the display changes. klik_pos.api.pos_entry.create_closing_entry
recomputes expected amounts on the server, so the POS Closing Entry and its
reconciliation are unaffected.
"""

import frappe

# Roles that keep seeing expected amounts and variance when closing.
MANAGER_ROLES = {"System Manager", "Accounts Manager"}


@frappe.whitelist()
def blind_close_settings():
	"""Whether the current user's Close Shift dialog must hide expected amounts."""
	from klik_pos.api.pos_profile import get_pos_details

	details = get_pos_details() or {}
	hide = bool(details.get("custom_hide_expected_amount"))
	is_manager = bool(MANAGER_ROLES & set(frappe.get_roles()))
	return {"hide": hide and not is_manager}
