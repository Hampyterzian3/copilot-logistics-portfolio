// Dark/light theme. Loaded without defer in <head> so the theme is set before first paint.
// First visit is light; a click on any [data-theme-toggle] button saves the choice.
(function () {
  var KEY = "hampy-theme";
  var DEFAULT = "light";
  var root = document.documentElement;

  function saved() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }

  function apply(theme) {
    root.setAttribute("data-theme", theme);
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", theme === "light" ? "#fffdf8" : "#0c2c23");
    document.querySelectorAll("[data-theme-toggle]").forEach(function (b) {
      b.setAttribute("aria-pressed", String(theme === "dark"));
      b.title = theme === "dark" ? "Switch to light mode" : "Switch to dark mode";
    });
  }

  var s = saved();
  apply(s === "light" || s === "dark" ? s : DEFAULT);

  document.addEventListener("DOMContentLoaded", function () {
    apply(root.getAttribute("data-theme"));
    document.querySelectorAll("[data-theme-toggle]").forEach(function (b) {
      b.addEventListener("click", function () {
        var next = root.getAttribute("data-theme") === "light" ? "dark" : "light";
        try { localStorage.setItem(KEY, next); } catch (e) { /* storage blocked: still switch for this page */ }
        apply(next);
      });
    });
  });
})();
