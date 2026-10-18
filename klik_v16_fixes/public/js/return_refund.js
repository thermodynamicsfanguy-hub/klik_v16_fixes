// Return screens for credit invoices — see klik_v16_fixes/returns.py.
// KLiK's return dialogs treat an unpaid invoice as fully paid (they fall back
// to the invoice total when paid_amount is 0) and pre-fill a cash refund for
// everything returned. On the server returns.py credits what is still owed
// first and refunds only the rest; this script makes both dialogs show that:
// - Return Items (one invoice): the refund box is set to (returned - owed),
//   KLiK's labels are renamed, and the success toast states the real refund.
// - Multi-Invoice Return: each selected invoice's Amount box is set the same
//   way with a line under it, and a "Cash to refund" total is shown next to
//   KLiK's Total Return Amount.
// Invoices with nothing owed are left exactly as KLiK shows them. KLiK's
// labels are hard-coded English, so the match is on the text (compat.py
// checks KLiK's bundle still contains them); if KLiK changes that markup the
// dialogs fall back to KLiK's figures and the server still books the right
// refund.
(function () {
	const SINGLE_TITLE = "Return Items";
	const MULTI_TITLE = "Multi-Invoice Return";
	const RENAME = { "Paid Amount:": "Cash refund:", "Write-off:": "Deducted from balance:" };
	const NOTE_ATTR = "data-klik-v16-fixes-owed";
	const CASH_ATTR = "data-klik-v16-fixes-cash-total";
	const REFUND_INPUT = 'input[type="number"][step="0.01"]';
	const INVOICE_NAME = /^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+$/; // e.g. ACC-SINV-2026-00024
	const TOAST = /^Return created successfully \((.+)\)$/;
	const basis = {}; // invoice -> {owed, paid} | "loading" | null
	let lastRefund = null; // single dialog: {zero, text, method} last set by this script

	function amount(text) {
		const m = (text || "").replace(/,/g, "").match(/-?\d+(?:\.\d+)?/);
		return m ? parseFloat(m[0]) : NaN;
	}

	function money(template, value) {
		// Reuse KLiK's own currency formatting: swap the number in an existing figure.
		return template.replace(/-?[\d,]+(?:\.\d+)?/, value.toFixed(2));
	}

	function round2(value) {
		return Math.round(value * 100) / 100;
	}

	function getBasis(invoice) {
		if (!(invoice in basis)) {
			basis[invoice] = "loading";
			fetch("/api/method/klik_v16_fixes.returns.refund_basis?invoice=" + encodeURIComponent(invoice), {
				credentials: "same-origin",
				headers: { Accept: "application/json" },
			})
				.then((r) => (r.ok ? r.json() : null))
				.then((r) => {
					basis[invoice] = r && r.message ? r.message : null;
					schedule();
				})
				.catch(() => {
					basis[invoice] = null;
				});
		}
		const info = basis[invoice];
		return info && info !== "loading" ? info : null;
	}

	function setInput(input, value) {
		if (Math.abs(parseFloat(input.value || "0") - value) < 0.005) return;
		const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
		setter.call(input, String(value));
		input.dispatchEvent(new Event("input", { bubbles: true }));
	}

	function setNote(parent, text, className) {
		let note = parent.querySelector(":scope > [" + NOTE_ATTR + "]");
		if (!note) {
			note = document.createElement("div");
			note.setAttribute(NOTE_ATTR, "1");
			note.className = className;
			parent.appendChild(note);
		}
		if (note.textContent !== text) note.textContent = text;
	}

	function dialogFor(title) {
		// Cheap check first: refund boxes only exist while a return dialog is open.
		for (const input of document.querySelectorAll(REFUND_INPUT)) {
			for (let el = input.parentElement; el && el !== document.body; el = el.parentElement) {
				const text = el.textContent;
				if (!text.includes(title)) continue;
				if (title === SINGLE_TITLE && (text.includes(MULTI_TITLE) || !text.includes("Invoice:"))) break;
				return el;
			}
		}
		return null;
	}

	// ---- Return Items (one invoice) ----

	function singleTotal(dialog) {
		for (const span of dialog.querySelectorAll("span")) {
			if (span.textContent.trim() === "Total Return Amount:" && span.nextElementSibling) {
				return span.nextElementSibling;
			}
		}
		return dialog.querySelector(".text-right .text-lg");
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

	function applySingle(dialog) {
		const m = dialog.textContent.match(/Invoice:\s*([A-Za-z0-9-]+)/);
		if (!m) return;
		const info = getBasis(m[1]);
		if (!info) return;
		if (!(info.owed > 0)) {
			lastRefund = null;
			return;
		}

		const totalEl = singleTotal(dialog);
		const input = dialog.querySelector(REFUND_INPUT);
		if (!totalEl || !input) return;
		const returned = amount(totalEl.textContent);
		if (isNaN(returned)) return;
		const template = totalEl.textContent.trim();

		const refund = Math.max(round2(returned - info.owed), 0);
		setInput(input, refund);
		const method = dialog.querySelector("select");
		lastRefund = { zero: refund === 0, text: money(template, refund), method: method ? method.value : "" };

		dialog.querySelectorAll("span").forEach((span) => {
			const label = span.textContent.trim();
			if (RENAME[label]) span.textContent = RENAME[label];
		});

		const header = totalEl.closest(".text-right");
		if (header) {
			setNote(
				header,
				"Customer owes: " + money(template, info.owed) + " · Paid: " + money(template, info.paid),
				"text-xs text-gray-500 dark:text-gray-400 mt-1"
			);
		}
	}

	// ---- Multi-Invoice Return ----

	function invoiceCards(dialog) {
		const cards = [];
		dialog.querySelectorAll("h4").forEach((h4) => {
			const name = h4.textContent.trim();
			if (!INVOICE_NAME.test(name)) return;
			const card = h4.closest(".rounded-lg");
			if (card) cards.push({ name, card });
		});
		return cards;
	}

	function cardReturned(card) {
		// Last cell of each item row is KLiK's "Amount" (return qty x rate).
		let sum = 0;
		card.querySelectorAll("tbody tr").forEach((row) => {
			const cells = row.querySelectorAll("td");
			const value = cells.length ? amount(cells[cells.length - 1].textContent) : NaN;
			if (!isNaN(value)) sum += value;
		});
		return round2(sum);
	}

	function cardTemplate(card) {
		const cell = card.querySelector("tbody tr td:last-child");
		return cell ? cell.textContent.trim() : "0.00";
	}

	function applyMulti(dialog) {
		let cashTotal = 0;
		let anyAdjusted = false;
		let template = null;

		invoiceCards(dialog).forEach(({ name, card }) => {
			const input = card.querySelector(REFUND_INPUT);
			if (!input) return; // invoice not selected
			template = template || cardTemplate(card);
			const info = getBasis(name);
			if (info && info.owed > 0) {
				const returned = cardReturned(card);
				const refund = Math.max(round2(returned - info.owed), 0);
				setInput(input, refund);
				anyAdjusted = true;

				const box = input.closest(".relative") ? input.closest(".relative").parentElement : null;
				const label = box && box.querySelector("label");
				if (label && label.textContent.trim() === "Amount") label.textContent = "Cash refund";
				if (box) {
					const t = cardTemplate(card);
					setNote(
						box,
						"Owes " + money(t, info.owed) + " · Paid " + money(t, info.paid) +
							" · Deducted from balance " + money(t, round2(Math.min(returned, info.owed))),
						"text-xs text-gray-500 dark:text-gray-400 mt-1"
					);
				}
			}
			cashTotal += parseFloat(input.value || "0") || 0;
		});

		// "Cash to refund" next to KLiK's Total Return Amount, once any figure was corrected.
		for (const p of dialog.querySelectorAll("p")) {
			if (p.textContent.trim() !== "Total Return Amount") continue;
			const box = p.parentElement;
			if (!box) break;
			const existing = box.querySelector(":scope > [" + CASH_ATTR + "]");
			if (!anyAdjusted || !template) {
				if (existing) existing.remove();
				break;
			}
			let line = existing;
			if (!line) {
				line = document.createElement("p");
				line.setAttribute(CASH_ATTR, "1");
				line.className = "text-sm font-semibold text-orange-600 dark:text-orange-400";
				box.appendChild(line);
			}
			const text = "Cash to refund: " + money(template, round2(cashTotal));
			if (line.textContent !== text) line.textContent = text;
			break;
		}
	}

	function apply() {
		fixToast();
		const multi = dialogFor(MULTI_TITLE);
		if (multi) return applyMulti(multi);
		const single = dialogFor(SINGLE_TITLE);
		if (single) applySingle(single);
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
