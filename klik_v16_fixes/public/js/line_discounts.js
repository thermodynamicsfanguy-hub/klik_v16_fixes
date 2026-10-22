// Cart: a seller's line discount survives a page reload. KLiK keeps manual
// line discounts (Discount Amount / %, a typed rate, a line price list) only
// in OrderSummary's React state, so a reload brings the cart back at list
// price with no sign that anything was lost; it also seeds that state from
// the pricing rule's discount_percentage, so a rule discount is applied twice
// on the already-discounted price. This script reads each cart row's state
// from its props (CartItemRow: itemId, item, itemDiscount), saves it under
// its own key, and when a row is mounted again (reload, or back from another
// screen) puts the saved values back through the row's own handlers
// (onCustomRateChange, onDiscountChange) and says so. If KLiK's markup
// changes, nothing is restored and the cart behaves as before (compat.py
// checks the names).
(function () {
	const KEY = "klik_v16_fixes-line-discounts";
	const CART_KEY = "beveren-cart-storage";
	const NOTE_ATTR = "data-klik-v16-fixes-discounts-note";
	const FIELDS = ["discountPercentage", "discountAmount", "selectedPriceList"];
	const seen = new WeakSet(); // row elements already restored or recorded

	function load() {
		try {
			const saved = JSON.parse(localStorage.getItem(KEY) || "{}");
			return saved && typeof saved === "object" ? saved : {};
		} catch (e) {
			return {};
		}
	}

	function store(lines) {
		try {
			if (Object.keys(lines).length) localStorage.setItem(KEY, JSON.stringify(lines));
			else localStorage.removeItem(KEY);
		} catch (e) {
			// storage full or blocked: the cart works as KLiK's own
		}
	}

	function cartIds() {
		try {
			const cart = JSON.parse(localStorage.getItem(CART_KEY) || "{}");
			return new Set(((cart.state && cart.state.cartItems) || []).map((i) => i.id));
		} catch (e) {
			return null;
		}
	}

	function rowProps(el) {
		const key = Object.keys(el).find((k) => k.startsWith("__reactFiber$"));
		let fiber = key && el[key];
		for (let i = 0; fiber && i < 5; i++, fiber = fiber.return) {
			const p = fiber.memoizedProps;
			if (p && p.itemId && p.item && p.itemDiscount && p.onDiscountChange && p.onCustomRateChange) return p;
		}
		return null;
	}

	function rows() {
		const found = new Map();
		for (const el of document.querySelectorAll("[data-cart-item-id]")) {
			const p = rowProps(el);
			if (p && !found.has(p.itemId)) found.set(p.itemId, { el, p });
		}
		return found;
	}

	// The cart line as KLiK persists it: a saved discount is put back only on the same line
	function lineOf(item) {
		return [item.item_code || item.id, item.uom || "", item.quantity, item.price, item.discount_percentage || 0, item.discount_amount || 0, item.custom_rate ?? null].join("|");
	}

	function snapshot(p) {
		const d = p.itemDiscount;
		const rate = d.customRate === undefined || d.customRate === null ? null : Number(d.customRate);
		return {
			line: lineOf(p.item),
			discountPercentage: Number(d.discountPercentage) || 0,
			discountAmount: Number(d.discountAmount) || 0,
			selectedPriceList: d.selectedPriceList || "",
			customRate: rate,
			customRateIncludesTax: rate === null ? null : d.customRateIncludesTax !== false,
		};
	}

	function isManual(saved) {
		return saved.discountAmount > 0 || saved.customRate !== null || !!saved.selectedPriceList;
	}

	// Put the saved values back; true when they carried a seller discount that was missing.
	function restore(p, saved) {
		const now = snapshot(p);
		if (now.line !== saved.line) return false;
		const lost = isManual(saved) && JSON.stringify(now) !== JSON.stringify(saved);
		// onCustomRateChange clears the discount fields, so it goes first and the rest follow
		const rateChanged = now.customRate !== saved.customRate || now.customRateIncludesTax !== saved.customRateIncludesTax;
		if (rateChanged) {
			p.onCustomRateChange(p.item, saved.customRate === null ? undefined : saved.customRate, saved.customRateIncludesTax);
		}
		for (const field of FIELDS) {
			if (rateChanged || now[field] !== saved[field]) p.onDiscountChange(p.itemId, field, saved[field]);
		}
		return lost;
	}

	function notify(count) {
		let note = document.querySelector("[" + NOTE_ATTR + "]");
		if (!note) {
			note = document.createElement("div");
			note.setAttribute(NOTE_ATTR, "1");
			note.setAttribute("role", "status");
			note.style.cssText =
				"position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:10000;max-width:90vw;" +
				"padding:10px 16px;border-radius:8px;background:#1e3a8a;color:#fff;font-size:14px;box-shadow:0 4px 12px rgba(0,0,0,.3)";
			document.body.appendChild(note);
		}
		note.textContent =
			"Seller discount restored on " + count + (count === 1 ? " line" : " lines") + " — check the cart before checkout";
		clearTimeout(note._timer);
		note._timer = setTimeout(() => note.remove(), 8000);
	}

	function sync() {
		const saved = load();
		const current = rows();
		let restored = 0;
		const lines = {};
		for (const [id, { el, p }] of current) {
			if (!seen.has(el)) {
				seen.add(el);
				// a row mounted again starts from KLiK's defaults: put the seller's values back
				if (saved[id] && restore(p, saved[id])) restored++;
				if (saved[id]) {
					lines[id] = saved[id];
					continue; // the handlers' update shows up on the next pass
				}
			}
			lines[id] = snapshot(p);
		}
		if (!current.size) {
			// cart not on screen (another page, drawer closed): keep lines still in the cart
			const ids = cartIds();
			for (const id in saved) if (!ids || ids.has(id)) lines[id] = saved[id];
		}
		store(lines);
		if (restored) notify(restored);
	}

	let queued = false;
	function schedule() {
		if (queued) return;
		queued = true;
		setTimeout(() => {
			queued = false;
			sync();
		}, 100);
	}

	function start() {
		sync();
		new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
		document.addEventListener("input", schedule, true);
		document.addEventListener("change", schedule, true);
		setInterval(sync, 1000); // state changes that touch no DOM node
		window.addEventListener("pagehide", sync);
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
	else start();
})();
