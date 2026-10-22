// Payments screen: never show balances that are already out of date.
// KLiK's Payment Entries page (By Invoice / By Customer / Reconcile) loads each
// tab's lists once, and after a payment or a reconciliation reloads only the
// list in that tab. The other tabs keep showing paid invoices as unpaid and
// allocated payments as unallocated, so a seller can collect cash for an
// invoice that is already settled (the server then refuses to record it, but
// the cash has changed hands). This reloads the page:
// - after KLiK confirms a payment ("Payment received: ...") or a
//   reconciliation ("Payment reconciled successfully."), once the toast has
//   been seen;
// - when the seller switches tab and the page was loaded over a minute ago,
//   since other sellers may have collected in the meantime.
// KLiK remembers the open tab across reloads. The toast texts are checked by
// compat.py; if KLiK changes them the page simply behaves as before.
(function () {
	const PATH = "/klik_pos/payments";
	const DONE = [/^Payment received: /, /^Payment reconciled successfully\.$/];
	const TABS = new Set(["By Invoice", "By Customer", "Reconcile"]);
	const STALE_MS = 60 * 1000;
	const TOAST_SEEN_MS = 1500;
	let loadedAt = Date.now();
	let reloading = false;

	function onPaymentsPage() {
		return window.location.pathname.startsWith(PATH);
	}

	function reload(delay) {
		if (reloading) return;
		reloading = true;
		setTimeout(() => window.location.reload(), delay);
	}

	function checkToasts() {
		if (reloading || !onPaymentsPage()) return;
		for (const toast of document.querySelectorAll(".Toastify__toast")) {
			const text = klikV16Text(toast).trim();
			if (DONE.some((re) => re.test(text))) return reload(TOAST_SEEN_MS);
		}
	}

	document.addEventListener(
		"click",
		(event) => {
			if (!onPaymentsPage() || Date.now() - loadedAt < STALE_MS) return;
			const button = event.target.closest && event.target.closest("button");
			if (button && TABS.has(klikV16Text(button).trim())) reload(0);
		},
		true
	);

	// KLiK is a single-page app: count "loaded" from when the payments page was entered.
	let lastPath = window.location.pathname;
	function trackNavigation() {
		if (window.location.pathname !== lastPath) {
			lastPath = window.location.pathname;
			loadedAt = Date.now();
		}
	}

	let queued = false;
	function schedule() {
		if (queued) return;
		queued = true;
		setTimeout(() => {
			queued = false;
			trackNavigation();
			checkToasts();
		}, 100);
	}

	function start() {
		new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
	else start();
})();
