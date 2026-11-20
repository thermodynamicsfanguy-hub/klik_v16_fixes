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


class ReportingDeferred(Exception):
	"""The gateway is out and the invoice was marked PENDING."""


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
		try:
			return _post(config["zatca_environment"].invoice_clearance_api, config, payload, module)
		except requests.exceptions.RequestException:
			frappe.local.message_log = []  # the app said «sent to ZATCA» before sending: nothing was
			frappe.throw(OUTAGE_MESSAGE)

	def on_submit(doc, method=None):
		try:
			original_hook(doc, method)
		except ReportingDeferred:
			frappe.msgprint("منصة الزكاة غير متاحة الآن: رُحّلت الفاتورة وستُبلَّغ تلقائياً عند عودتها.", alert=True)

	module._submit_reporting_request = submit_reporting
	module._submit_clearance_request = submit_clearance
	module.generate_einvoice_on_submit = on_submit
	setattr(module, _PATCHED_FLAG, True)
