// Checkout dialog: credit sales default to the customer's payment terms — see
// klik_v16_fixes/terms.py. KLiK pre-fills "Due Date" with today when "Is
// Credit Sale" is switched on. When the customer has payment terms, this
// script replaces that default once per dialog with the date from the terms
// and shows which terms it came from; the seller can still change it. The
// selected customer is read from KLiK's persisted cart (beveren-cart-storage).
// If KLiK's markup or storage changes, the dialog keeps today and the server
// still applies the terms (compat.py checks both).
(function () {
	const CREDIT_ON = "Credit Sale Enabled";
	const CART_KEY = "beveren-cart-storage";
	const DONE_ATTR = "data-klik-v16-fixes-terms";
	const NOTE_ATTR = "data-klik-v16-fixes-terms-note";
	const cache = {}; // customer -> {due_date, terms} | "loading" | null

	function today() {
		const d = new Date();
		const pad = (n) => String(n).padStart(2, "0");
		return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
	}

	function selectedCustomer() {
		try {
			const cart = JSON.parse(localStorage.getItem(CART_KEY) || "{}");
			const customer = cart.state && cart.state.selectedCustomer;
			return customer && customer.id ? customer.id : null;
		} catch (e) {
			return null;
		}
	}

	function termsFor(customer) {
		if (!(customer in cache)) {
			cache[customer] = "loading";
			fetch("/api/method/klik_v16_fixes.terms.default_due_date?customer=" + encodeURIComponent(customer), {
				credentials: "same-origin",
				headers: { Accept: "application/json" },
			})
				.then((r) => (r.ok ? r.json() : null))
				.then((r) => {
					cache[customer] = r && r.message ? r.message : null;
					schedule();
				})
				.catch(() => {
					cache[customer] = null;
				});
		}
		const info = cache[customer];
		return info && info !== "loading" ? info : null;
	}

	function setDate(input, value) {
		const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
		setter.call(input, value);
		input.dispatchEvent(new Event("input", { bubbles: true }));
		input.dispatchEvent(new Event("change", { bubbles: true }));
	}

	function apply() {
		for (const button of document.querySelectorAll("button")) {
			if (button.textContent.trim() !== CREDIT_ON) continue;
			const box = button.parentElement;
			const input = box && box.querySelector('input[type="date"]');
			if (!input || input.disabled || input.hasAttribute(DONE_ATTR)) continue;
			const customer = selectedCustomer();
			if (!customer) continue;
			const info = termsFor(customer);
			if (!info) continue;
			input.setAttribute(DONE_ATTR, "1"); // once per dialog: the seller may change it afterwards
			if (!info.due_date || input.value !== today()) continue;
			setDate(input, info.due_date);
			let note = box.querySelector("[" + NOTE_ATTR + "]");
			if (!note) {
				note = document.createElement("div");
				note.setAttribute(NOTE_ATTR, "1");
				note.className = "text-xs text-gray-500 dark:text-gray-400 mt-1";
				input.insertAdjacentElement("afterend", note);
			}
			note.textContent = "From the customer's payment terms (" + info.terms + ")";
		}
	}

	let queued = false;
	function schedule() {
		if (queued) return;
		queued = true;
		setTimeout(() => {
			queued = false;
			apply();
		}, 50);
	}

	function start() {
		apply();
		new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
	else start();
})();
