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

import json
import time

import frappe
import requests
from requests.auth import HTTPBasicAuth

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


class ReportingDeferred(Exception):
	"""The gateway is out and the invoice was marked PENDING."""


def _not_sent(error):
	"""True when the request cannot have reached ZATCA."""
	if isinstance(error, (requests.exceptions.ConnectTimeout, requests.exceptions.SSLError)):
		return True
	if isinstance(error, requests.exceptions.ConnectionError) and not isinstance(error, requests.exceptions.Timeout):
		from urllib3.exceptions import NewConnectionError

		reason = getattr(error.args[0], "reason", None) if error.args else None
		return isinstance(reason, NewConnectionError)  # refused or no such host (NameResolutionError)
	return False


class _Cleared:
	"""ZATCA's 208 «previously submitted», handed to the app as the 200 «CLEARED» it stands for."""

	status_code = 200

	def __init__(self, response, body):
		results = {"status": "PASS", "errorMessages": [], "warningMessages": [], "infoMessages": [{
			"type": "INFO", "code": "INVOICE_HASH_PREVIOUSLY_SUBMITTED", "status": "PASS",
			"message": "ZATCA 208: cleared on an earlier send whose answer was lost"}]}
		self._body = dict(body, clearanceStatus="CLEARED", validationResults=results, seeve_zatca_answer=208)
		self.text = response.text

	def json(self):
		return self._body


def _as_cleared(response):
	"""A 208 carrying the cleared invoice, as a 200; None when it carries none (nothing to print)."""
	try:
		body = response.json()
	except Exception:
		return None
	return _Cleared(response, body) if body.get("clearedInvoice") else None


def _post(url, config, payload, module):
	started = time.time()
	response = requests.post(
		url, headers=module.get_clearence_headers(),
		auth=HTTPBasicAuth(config["production_csid"].binary_security_token, config["production_csid"].secret),
		json=payload, timeout=TIMEOUT,
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
		for attempt in range(1 + RESENDS):
			if attempt:
				time.sleep(RESEND_PAUSE)
			try:
				response, took = _post(url, config, payload, module)
			except requests.exceptions.RequestException as error:
				if attempt == 0 and _not_sent(error):
					frappe.local.message_log = []  # the app said «sent to ZATCA» before sending: nothing was
					frappe.throw(OUTAGE_MESSAGE)
				continue  # it may be at ZATCA: the same payload again, never a new signature
			if response.status_code >= 500:
				continue  # a gateway error may follow a clearance ZATCA kept: the same payload again
			if response.status_code == 208:
				response = _as_cleared(response)
				if response is None:
					break
			if attempt:
				frappe.logger("zatca").info(f"seeve clearance answered {response.status_code} on resend {attempt} "
					f"(uuid {payload.get('uuid')})")
			return response, took
		frappe.logger("zatca").error("seeve clearance: answer unknown after resends; ZATCA may hold it. " + json.dumps({
			"device": frappe.flags.get("seeve_zatca_device"), "uuid": payload.get("uuid"),
			"invoiceHash": payload.get("invoiceHash"), "payload": payload}))
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
