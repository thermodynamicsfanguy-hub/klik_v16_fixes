"""Blind shift close for KLiK PoS, without editing klik_pos.

KLiK's POS Profile option "Hide Expected Amount" (custom_hide_expected_amount)
hides the payment summary on the closing page, but its Close Shift dialog
still prints "Expected" and "Variance" — and the variance alone gives the
expected amount away. The cashier should count without knowing the target.

KLiK serves /klik_pos as a standalone HTML page, so web_include_js never
reaches it. Instead an after_request hook adds one <script> to that page, and
the script asks blind_close_settings() whether to hide the two figures.

Only the display changes. klik_pos.api.pos_entry.create_closing_entry
recomputes expected amounts on the server, so the POS Closing Entry and its
reconciliation are unaffected.
"""

import hashlib
from pathlib import Path

import frappe

SCRIPT = Path(__file__).resolve().parent / "public" / "js" / "klik_blind_close.js"
SCRIPT_URL = "/assets/klik_v16_fixes/js/blind_close.js"
# Roles that keep seeing expected amounts and variance when closing.
MANAGER_ROLES = {"System Manager", "Accounts Manager"}

_version = None


def _script_tag():
	global _version
	if _version is None:
		_version = hashlib.sha1(SCRIPT.read_bytes()).hexdigest()[:10]
	return f'<script src="{SCRIPT_URL}?v={_version}"></script>'


def inject_into_klik_page(response, request):
	"""after_request hook: add the blind-close script to KLiK's SPA page."""
	if not request.path.startswith("/klik_pos") or request.path.startswith("/klik_pos/api"):
		return
	if response.status_code != 200 or response.mimetype != "text/html" or response.direct_passthrough:
		return
	body = response.get_data(as_text=True)
	if "</body>" not in body or SCRIPT_URL in body:
		return
	response.set_data(body.replace("</body>", _script_tag() + "</body>", 1))


@frappe.whitelist()
def blind_close_settings():
	"""Whether the current user's Close Shift dialog must hide expected amounts."""
	from klik_pos.api.pos_profile import get_pos_details

	details = get_pos_details() or {}
	hide = bool(details.get("custom_hide_expected_amount"))
	is_manager = bool(MANAGER_ROLES & set(frappe.get_roles()))
	return {"hide": hide and not is_manager}
