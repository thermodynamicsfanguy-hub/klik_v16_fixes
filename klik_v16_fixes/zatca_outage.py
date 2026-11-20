"""Runtime fix: a ZATCA outage stops the counter, though a simplified invoice may wait.

zatca_integration reports inside before_submit and calls requests.post with no timeout. When
the gateway is unreachable the seller waits, then the sale is refused. A simplified (B2C)
invoice has 24 hours to be reported, and the app already has a state for "signed, QR made,
not reported yet": PENDING. A standard (B2B) invoice must be cleared before it is issued, so
that one still refuses, promptly and saying why.

This never edits zatca_integration. The two senders and the before_submit hook are looked up
as module globals at call time, so they are swapped for versions with a timeout. A reporting
outage (no connection, or the gateway answering 5xx) marks the invoice PENDING the way the app
does, and whatever retries PENDING invoices calls generate_einvoice again as the app does.
"""

import base64
import json
import time

import frappe
import requests
from requests.auth import HTTPBasicAuth
from urllib3.exceptions import NewConnectionError

MODULE = "zatca_integration.clearence_util"
TIMEOUT = 20
_PATCHED_FLAG = "_klik_v16_fixes_zatca_outage"
OUTAGE_MESSAGE = (
	"تعذّر الوصول إلى منصة الزكاة والضريبة. الفاتورة الضريبية للمنشآت تُعتمد قبل إصدارها، "
	"فلم تُرحَّل. احفظها مسودة وأعد المحاولة بعد قليل، أو أصدرها بعد عودة الاتصال."
)


UNKNOWN_MESSAGE = (
	"أُرسلت فاتورة المنشأة لمنصة الزكاة ولم يصل ردها بعد ثلاث محاولات، فلم تُرحَّل. قد تكون المنصة اعتمدتها: "
	"لا تُصدرها من جديد الآن، وبلّغ المحاسب بالعميل والمبلغ والوقت."
)
# A clearance whose answer was lost (a read timeout, a reset connection, a gateway 5xx) may be at ZATCA.
# Signing again would give the same invoice a second hash: two invoices at ZATCA, one needing a credit
# note. ZATCA answers the same hash within 24 hours with 208 and the cleared invoice it kept (simulation
# since 2025-05, production since 2025-08; the developer portal answers 200 again), so the same payload
# is sent again (2026-11-20). An error before anything left (no connection, name, TLS) is the outage.
RESENDS = 2
RESEND_PAUSE = 2
# The sale holds its till's device row (FOR UPDATE) while it waits: a second cashier on that till waits too
# (innodb_lock_wait_timeout: 50 s on storelab, 15 s on the shared host, then retry_busy). So one budget for
# all the attempts, and a connect timeout apart from the read timeout (requests applies each per phase).
CONNECT_TIMEOUT = 5
ATTEMPT_MAX = CONNECT_TIMEOUT + TIMEOUT
BUDGET = 50


class ReportingDeferred(Exception):
	"""The gateway is out and the invoice was marked PENDING."""


def _not_sent(error):
	"""True when the request cannot have reached ZATCA: no connection was made (timeout, refused, no such
	host). A TLS error is not proof (urllib3 raises one too when the stream breaks while reading the answer),
	so it is resent (review 2026-11-20)."""
	if isinstance(error, requests.exceptions.ConnectTimeout):
		return True
	if isinstance(error, requests.exceptions.SSLError) or isinstance(error, requests.exceptions.Timeout):
		return False
	if isinstance(error, requests.exceptions.ConnectionError):
		reason = getattr(error.args[0], "reason", None) if error.args else None
		return isinstance(reason, NewConnectionError)  # refused, or no such host (NameResolutionError)
	return False


class _Cleared:
	"""ZATCA's 208 «previously submitted», handed to the app as the 200 «CLEARED» it stands for. ZATCA's own
	results stay in the body (seeve_zatca_original) for Zatca Transactions; its errors are left out of the
	app's copy because display_error_ui throws on any error message."""

	status_code = 200

	def __init__(self, response, body):
		original = body.get("validationResults") or {}
		results = {"status": "PASS", "errorMessages": [], "warningMessages": original.get("warningMessages") or [],
			"infoMessages": [{"type": "INFO", "code": "INVOICE_HASH_PREVIOUSLY_SUBMITTED", "status": "PASS",
				"message": "ZATCA 208: cleared on an earlier send whose answer was lost"}]}
		self._body = dict(body, clearanceStatus="CLEARED", validationResults=results, seeve_zatca_answer=208,
			seeve_zatca_original=original)
		self.text = response.text

	def json(self):
		return self._body


def _as_cleared(response, payload):
	"""A 208 whose cleared invoice is this very invoice, as a 200; None otherwise (nothing safe to print)."""
	try:
		body = response.json()
		if not isinstance(body, dict) or body.get("clearanceStatus") not in (None, "", "CLEARED"):
			return None
		xml = base64.b64decode(body.get("clearedInvoice") or "", validate=True).decode("utf-8")
	except Exception:
		return None
	if not xml or payload.get("uuid") not in xml:
		return None  # not the invoice we sent
	return _Cleared(response, body)


def _post(url, config, payload, module):
	started = time.time()
	response = requests.post(
		url, headers=module.get_clearence_headers(),
		auth=HTTPBasicAuth(config["production_csid"].binary_security_token, config["production_csid"].secret),
		json=payload, timeout=(CONNECT_TIMEOUT, TIMEOUT),
	)
	return response, {"duration": time.time() - started}


def _defer(doc, payload, module):
	module._save_qr_code(doc, module.decode_invoice(payload.get("invoice")))
	doc.custom_zatca_submit_status = "PENDING"
	raise ReportingDeferred


def apply():
	"""before_request / before_job hook: install the fix once per process."""
	try:
		module = frappe.get_module(MODULE)
	except ImportError:
		return
	if getattr(module, _PATCHED_FLAG, False):
		return
	original_hook = module.generate_einvoice_on_submit

	def submit_reporting(config, payload, doc):
		try:
			response, took = _post(config["zatca_environment"].invoice_reporting_api, config, payload, module)
		except requests.exceptions.RequestException:
			_defer(doc, payload, module)
		if response.status_code >= 500:
			_defer(doc, payload, module)
		return response, took

	def submit_clearance(config, payload):
		url = config["zatca_environment"].invoice_clearance_api
		started = time.time()
		seen = []  # what each attempt got, for the log
		for attempt in range(1 + RESENDS):
			if attempt:
				# a seller waiting at the till gets a shorter budget (seeve_flow.api.invoice, store_core
				# zatca_background phase 2); the queue takes over what is left
				if time.time() - started + RESEND_PAUSE + ATTEMPT_MAX > (frappe.flags.get("seeve_zatca_budget") or BUDGET):
					break  # the till's device row is held the whole time: no resend past the budget
				time.sleep(RESEND_PAUSE)
			try:
				response, took = _post(url, config, payload, module)
			except requests.exceptions.RequestException as error:
				seen.append(type(error).__name__)
				if attempt == 0 and _not_sent(error):
					frappe.local.message_log = []  # the app said «sent to ZATCA» before sending: nothing was
					frappe.throw(OUTAGE_MESSAGE)
				continue  # it may be at ZATCA: the same payload again, never a new signature
			seen.append(response.status_code)
			took = {"duration": time.time() - started}
			if response.status_code == 208:
				cleared = _as_cleared(response, payload)
				if cleared is not None:
					return cleared, took
				break  # a 208 we cannot use: unknown, never the app's FAILED path
			if attempt == 0 and response.status_code < 500:
				return response, took  # the first answer, whatever it is, is the app's to handle as before
			if response.status_code in (200, 202):
				frappe.logger("zatca").info(f"seeve clearance {seen} (uuid {payload.get('uuid')})")
				return response, took
			# a resend answered 4xx (409, 429, a «duplicate» 400 …) or any 5xx: the first may still be at
			# ZATCA. Handing it to the app would commit FAILED inside the sale (update_status_on_error) and
			# tell the seller to fix and resubmit, i.e. sign a second invoice (review 2026-11-20).
		frappe.logger("zatca").error("seeve clearance: answer unknown; ZATCA may hold it. " + json.dumps({
			"attempts": seen, "device": frappe.flags.get("seeve_zatca_device"), "uuid": payload.get("uuid"),
			"invoiceHash": payload.get("invoiceHash"), "payload": payload}, default=str))
		frappe.local.message_log = []
		frappe.throw(UNKNOWN_MESSAGE)

	def on_submit(doc, method=None):
		try:
			original_hook(doc, method)
		except ReportingDeferred:
			frappe.msgprint("منصة الزكاة غير متاحة الآن: رُحّلت الفاتورة وستُبلَّغ تلقائياً عند عودتها.", alert=True)

	module._submit_reporting_request = submit_reporting
	module._submit_clearance_request = submit_clearance
	module.generate_einvoice_on_submit = on_submit
	setattr(module, _PATCHED_FLAG, True)
