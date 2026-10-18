// Close Shift: show the expected amount the closing entry will be checked
// against — see klik_v16_fixes/closing.py. KLiK computes "Expected" in the
// browser from the shift's invoice payments only: no opening float, no change
// given back, no money collected on earlier credit sales. Its "Variance" is
// counted minus that. When the Close Shift dialog or the closing page shows
// those figures (i.e. not under blind close), this script replaces Expected
// with shift_expected() from the server and recomputes Variance as the counted
// amount changes. KLiK's labels are matched as text (checked by compat.py);
// if they change, KLiK's own figures show again.
(function () {
	const EXPECTED = "Expected";
	const VARIANCE = "Variance";
	const FIXED_ATTR = "data-klik-v16-fixes-expected";
	let expected = null; // {mode: amount} for the open shift
	let loading = false;
	let loadedFor = 0; // time of the last fetch, refreshed per dialog opening

	function amount(text) {
		const m = (text || "").replace(/,/g, "").match(/-?\d+(?:\.\d+)?/);
		return m ? parseFloat(m[0]) : NaN;
	}

	function money(template, value) {
		return template.replace(/-?[\d,]+(?:\.\d+)?/, value.toFixed(2));
	}

	function load() {
		if (loading) return;
		loading = true;
		fetch("/api/method/klik_v16_fixes.closing.shift_expected", {
			credentials: "same-origin",
			headers: { Accept: "application/json" },
		})
			.then((r) => (r.ok ? r.json() : null))
			.then((r) => {
				const msg = r && r.message;
				expected = msg && !msg.hidden ? msg.expected || {} : null;
				loadedFor = Date.now();
				loading = false;
				schedule();
			})
			.catch(() => {
				loading = false;
			});
	}

	function labelCells(name) {
		return [...document.querySelectorAll("div.text-xs")].filter(
			(d) => d.textContent.trim() === name && d.offsetParent !== null
		);
	}

	function apply() {
		const expectedLabels = labelCells(EXPECTED);
		if (!expectedLabels.length) {
			loadedFor = 0; // dialog closed: fetch fresh figures next time
			return;
		}
		if (!loadedFor) return load();
		if (!expected) return;

		for (const label of expectedLabels) {
			const row = label.closest(".grid");
			const value = label.nextElementSibling;
			const nameEl = row && row.querySelector(".font-medium");
			if (!row || !value || !nameEl) continue;
			const mode = nameEl.textContent.trim();
			if (!(mode in expected)) continue;

			const target = expected[mode];
			const template = value.getAttribute(FIXED_ATTR) || value.textContent.trim();
			value.setAttribute(FIXED_ATTR, template);
			const text = money(template, target);
			if (value.textContent !== text) value.textContent = text;

			const varianceLabel = [...row.querySelectorAll("div.text-xs")].find((d) => d.textContent.trim() === VARIANCE);
			const counted = row.querySelector('input[type="number"]');
			const varianceEl = varianceLabel && varianceLabel.nextElementSibling;
			if (!varianceEl || !counted) continue;
			const variance = Math.round(((parseFloat(counted.value) || 0) - target) * 100) / 100;
			const vText = money(template, variance);
			if (varianceEl.textContent !== vText) varianceEl.textContent = vText;
			varianceEl.style.color = variance === 0 ? "" : variance < 0 ? "#dc2626" : "#d97706";
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
		document.addEventListener("input", schedule, true);
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
	else start();
})();
