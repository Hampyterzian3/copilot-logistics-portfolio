// Keyboard support for role="tab" widgets in the demos (WAI-ARIA tabs pattern, WCAG 4.1.2):
// roving tabindex, Left/Right arrows, Home/End. Selection still runs through each page's own click handler.
(function () {
  document.querySelectorAll('[role="tablist"]').forEach(function (list) {
    var tabs = Array.prototype.slice.call(list.querySelectorAll('[role="tab"]'));
    if (!tabs.length) return;
    function sync() {
      var any = tabs.some(function (t) { return t.getAttribute("aria-selected") === "true"; });
      tabs.forEach(function (t, i) { t.tabIndex = (any ? t.getAttribute("aria-selected") === "true" : i === 0) ? 0 : -1; });
    }
    list.addEventListener("keydown", function (e) {
      var i = tabs.indexOf(document.activeElement);
      if (i < 0) return;
      var n = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: tabs.length - 1 }[e.key];
      if (n === undefined) return;
      e.preventDefault();
      var t = tabs[(n + tabs.length) % tabs.length];
      t.click(); t.focus();
    });
    // Pages also switch tabs from the agent panel, so keep tabindex in step with aria-selected.
    new MutationObserver(sync).observe(list, { subtree: true, attributes: true, attributeFilter: ["aria-selected"] });
    sync();
  });
})();
