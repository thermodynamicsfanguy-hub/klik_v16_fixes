// The cart line's price labels, when tax is on the invoice and not on the item.
// KLiK labels its editable rate «Rate (Incl. Tax)» and the line «Amount (Incl. Tax)»
// whenever the item has no tax of its own (no Item Tax Template), and then shows the
// rate before the invoice's taxes: a shop with 15% VAT on the invoice read 420 as
// «including tax» beside a tile that says 483. When the line has no «Rate (Excl.
// Tax)» field (KLiK's sign that it knows the item's tax), the labels say «Rate» and
// «Amount», which is true whichever way the invoice's taxes are set.
(function () {
	const NEUTRAL = { "Rate (Incl. Tax)": "Rate", "Amount (Incl. Tax)": "Amount" };

	function apply() {
		for (const label of document.querySelectorAll("label")) {
			const to = NEUTRAL[klikV16Text(label).trim()];
			if (!to) continue;
			const block = (label.closest(".grid") || label).parentElement || label;
			const knowsItemTax = [...block.querySelectorAll("label")].some((l) => klikV16Text(l).trim() === "Rate (Excl. Tax)");
			if (!knowsItemTax) label.textContent = to;
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
		new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true, characterData: true });
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
	else start();
})();
