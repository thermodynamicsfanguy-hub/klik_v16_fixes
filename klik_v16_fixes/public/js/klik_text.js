// Lets a script that rewrites KLiK's text (a translation, a rename) coexist with
// the other page scripts here, which find KLiK's elements by their English labels.
// Such a script records each Text node's original in window.klikV16Originals
// (a WeakMap from Text node to string); klikV16Text(el) then returns el's text as
// KLiK wrote it. Without such a script it is plain textContent.
(function () {
	if (window.klikV16Text) return;
	const originals = (window.klikV16Originals = window.klikV16Originals || new WeakMap());
	window.klikV16Text = function (el) {
		if (!el) return "";
		if (el.nodeType === 3) return originals.has(el) ? originals.get(el) : el.nodeValue;
		let out = "";
		const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
		for (let n = walker.nextNode(); n; n = walker.nextNode()) out += originals.has(n) ? originals.get(n) : n.nodeValue;
		return out;
	};
})();
