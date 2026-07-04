/* Shared dark/light theme toggle. Include as a blocking <script> in <head>
   (before body renders) so the correct theme applies with no flash.
   Any element with class "theme-toggle-btn" toggles the theme on click;
   an inner element with [data-theme-icon] gets its icon class swapped. */
(function () {
  var STORAGE_KEY = "theme";

  function getPreferredTheme() {
    var stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    var icons = document.querySelectorAll("[data-theme-icon]");
    for (var i = 0; i < icons.length; i++) {
      icons[i].className = theme === "dark" ? "fas fa-sun" : "fas fa-moon";
    }
  }

  window.setAppTheme = function (theme) {
    localStorage.setItem(STORAGE_KEY, theme);
    applyTheme(theme);
  };

  window.toggleAppTheme = function () {
    var current = document.documentElement.getAttribute("data-theme") || "light";
    window.setAppTheme(current === "dark" ? "light" : "dark");
  };

  applyTheme(getPreferredTheme());

  document.addEventListener("DOMContentLoaded", function () {
    applyTheme(document.documentElement.getAttribute("data-theme") || getPreferredTheme());

    document.addEventListener("click", function (e) {
      var btn = e.target.closest && e.target.closest(".theme-toggle-btn");
      if (btn) window.toggleAppTheme();
    });

    if (!localStorage.getItem(STORAGE_KEY) && window.matchMedia) {
      window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function (e) {
        applyTheme(e.matches ? "dark" : "light");
      });
    }
  });
})();