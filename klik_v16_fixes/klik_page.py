"""Adds this app's scripts to KLiK's /klik_pos page.

KLiK serves /klik_pos as a standalone HTML page, so web_include_js never
reaches it. An after_request hook adds one <script> per file in SCRIPTS
instead, each versioned by its content hash.
"""

import hashlib
from pathlib import Path

JS_DIR = Path(__file__).resolve().parent / "public" / "js"
SCRIPTS = ("blind_close.js", "return_refund.js", "payments_refresh.js")  # see blind_close.py, returns.py and the script header
URL_PREFIX = "/assets/klik_v16_fixes/js/"

_tags = None


def _script_tags():
	global _tags
	if _tags is None:
		_tags = "".join(
			f'<script src="{URL_PREFIX}{name}?v={hashlib.sha1((JS_DIR / name).read_bytes()).hexdigest()[:10]}"></script>'
			for name in SCRIPTS
		)
	return _tags


def inject_into_klik_page(response, request):
	"""after_request hook: add the scripts to KLiK's SPA page."""
	if not request.path.startswith("/klik_pos") or request.path.startswith("/klik_pos/api"):
		return
	if response.status_code != 200 or response.mimetype != "text/html" or response.direct_passthrough:
		return
	body = response.get_data(as_text=True)
	if "</body>" not in body or URL_PREFIX in body:
		return
	response.set_data(body.replace("</body>", _script_tags() + "</body>", 1))
