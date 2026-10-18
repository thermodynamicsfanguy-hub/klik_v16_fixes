// Return screen for credit invoices — see klik_v16_fixes/returns.py.
// KLiK's Return Items dialog treats an unpaid invoice as fully paid
// ("Customer Paid" = the whole invoice) and pre-fills a cash refund for
// everything returned. On the server returns.py credits what is still owed
// first and refunds only the rest; this script makes the dialog show that:
// the refund box is set to (returned - owed) and KLiK's labels are renamed.
// Invoices with nothing owed are left exactly as KLiK shows them. KLiK's
// labels are hard-coded English, so the match is on the text; if KLiK changes
// that markup the dialog falls back to KLiK's figures (the server still books
// the right refund).
(function () {
	const TITLE = "Return Items";
	const RENAME = { "Paid Amount:": "Cash refund:", "Write-off:": "Deducted from balance:" };
	const NOTE_ATTR = "data-klik-v16-fixes-owed";
	const TOAST = /^Return created successfully \((.+)\)$/;
	const basis = {}; // invoice -> {owed, paid} | "loading"
	let lastRefund = null; // {text, method} for the dialog this script last corrected

	function amount(text) {
		const m = (text || "").replace(/,/g, "").match(/-?\d+(?:\.\d+)?/);
		return m ? parseFloat(m[0]) : NaN;
	}

	function money(template, value) {
		// Reuse KLiK's own currency formatting: swap the number in an existing figure.
		return template.replace(/-?[\d,]+(?:\.\d+)?/, value.toFixed(2));
	}

	function findDialog() {
		// Cheap check first: the 0.01-step refund box only exists while a return dialog is open.
		for (const input of document.querySelectorAll('input[type="number"][step="0.01"]')) {
			for (let el = input.parentElement; el && el !== document.body; el = el.parentElement) {
				if (el.textContent.includes(TITLE) && el.textContent.includes("Invoice:")) return el;
			}
		}
		return null;
	}

	function returnedTotal(dialog) {
		for (const span of dialog.querySelectorAll("span")) {
			if (span.textContent.trim() === "Total Return Amount:" && span.nextElementSibling) {
				return span.nextElementSibling;
			}
		}
		return dialog.querySelector(".text-right .text-lg");
	}

	function setInput(input, value) {
		if (Math.abs(parseFloat(input.value || "0") - value) < 0.005) return;
		const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
		setter.call(input, String(value));
		input.dispatchEvent(new Event("input", { bubbles: true }));
	}

	function fixToast() {
		// KLiK's success toast names the payment method even when nothing is refunded.
		if (!lastRefund) return;
		document.querySelectorAll(".Toastify__toast").forEach((toast) => {
			const body = toast.querySelector(".Toastify__toast-body > div:last-child") || toast;
			if (!TOAST.test(body.textContent.trim())) return;
			body.textContent = lastRefund.zero
				? "Return created: no cash refund, deducted from the customer's balance"
				: "Return created: cash refund " + lastRefund.text + " (" + lastRefund.method + ")";
		});
	}

	function apply() {
		fixToast();
		const dialog = findDialog();
		if (!dialog) return;
		const m = dialog.textContent.match(/Invoice:\s*([A-Za-z0-9-]+)/);
		if (!m) return;
		const invoice = m[1];

		if (!(invoice in basis)) {
			basis[invoice] = "loading";
			fetch(
				"/api/method/klik_v16_fixes.returns.refund_basis?invoice=" + encodeURIComponent(invoice),
				{ credentials: "same-origin", headers: { Accept: "application/json" } }
			)
				.then((r) => (r.ok ? r.json() : null))
				.then((r) => {
					basis[invoice] = r && r.message ? r.message : null;
					apply();
				})
				.catch(() => {
					basis[invoice] = null;
				});
			return;
		}
		const info = basis[invoice];
		if (info === "loading") return;
		if (!info || !(info.owed > 0)) {
			lastRefund = null;
			return;
		}

		const totalEl = returnedTotal(dialog);
		const input = dialog.querySelector('input[type="number"][step="0.01"]');
		if (!totalEl || !input) return;
		const returned = amount(totalEl.textContent);
		if (isNaN(returned)) return;

		const refund = Math.max(Math.round((returned - info.owed) * 100) / 100, 0);
		setInput(input, refund);
		const method = dialog.querySelector("select");
		lastRefund = {
			zero: refund === 0,
			text: money(totalEl.textContent.trim(), refund),
			method: method ? method.value : "",
		};

		dialog.querySelectorAll("span").forEach((span) => {
			const label = span.textContent.trim();
			if (RENAME[label]) span.textContent = RENAME[label];
		});

		const header = totalEl.closest(".text-right");
		if (header) {
			let note = header.querySelector("[" + NOTE_ATTR + "]");
			if (!note) {
				note = document.createElement("div");
				note.setAttribute(NOTE_ATTR, "1");
				note.className = "text-xs text-gray-500 dark:text-gray-400 mt-1";
				header.appendChild(note);
			}
			const text =
				"Customer owes: " + money(totalEl.textContent.trim(), info.owed) +
				" · Paid: " + money(totalEl.textContent.trim(), info.paid);
			if (note.textContent !== text) note.textContent = text;
		}
	}

	let queued = false;
	function schedule() {
		if (queued) return;
		queued = true;
		// A timer, not requestAnimationFrame: rAF pauses while the tab is in the background.
		setTimeout(() => {
			queued = false;
			apply();
		}, 50);
	}

	function start() {
		apply();
		new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true, characterData: true });
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
	else start();
})();
