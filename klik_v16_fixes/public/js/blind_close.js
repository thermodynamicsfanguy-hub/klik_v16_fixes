// Blind shift close for KLiK PoS — see klik_v16_fixes/blind_close.py.
// Hides the "Expected" and "Variance" figures in KLiK's Close Shift dialog
// when the server says so. KLiK renders those labels as hard-coded English
// text, so the match is on the exact label; if KLiK changes that markup the
// figures simply reappear (fail-open).
(function () {
	const LABELS = new Set(["Expected", "Variance"]);
	const STYLE_ID = "klik-v16-fixes-blind-close";
	let hide = null; // unknown until the server answers

	function apply(root) {
		if (hide !== true) return;
		root.querySelectorAll("div.text-xs").forEach((label) => {
			if (!LABELS.has(klikV16Text(label).trim())) return;
			const cell = label.parentElement;
			if (cell && cell.style.display !== "none") {
				cell.style.display = "none";
				cell.setAttribute("data-klik-v16-fixes-hidden", "1");
			}
		});
	}

	function start() {
		fetch("/api/method/klik_v16_fixes.blind_close.blind_close_settings", {
			credentials: "same-origin",
			headers: { Accept: "application/json" },
		})
			.then((r) => (r.ok ? r.json() : { message: { hide: false } }))
			.then((r) => {
				hide = !!(r.message && r.message.hide);
				if (!hide) return;
				if (!document.getElementById(STYLE_ID)) {
					const s = document.createElement("style");
					s.id = STYLE_ID;
					s.textContent = "[data-klik-v16-fixes-hidden]{display:none!important}";
					document.head.appendChild(s);
				}
				apply(document);
				new MutationObserver(() => apply(document)).observe(document.body, {
					childList: true,
					subtree: true,
				});
			})
			.catch(() => {});
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
	else start();
})();
