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
/* ── Scroll hint: bouncing ▼ arrow wherever more content is below ─────────────
   • Page level: floating button bottom-centre while the page can scroll down.
   • Element level: small arrow at the bottom of any scrollable box (lists,
     tables, side panels, modals). Click → smooth scroll down.
   Opt out on an element with  data-no-scroll-hint . */
(function () {
  var CSS =
    "@keyframes shBounce{0%,100%{transform:translateY(0)}50%{transform:translateY(5px)}}" +
    ".sh-arrow{position:fixed;z-index:10050;display:none;align-items:center;justify-content:center;" +
    "border:none;border-radius:50%;cursor:pointer;color:#fff;background:linear-gradient(135deg,#15803d,#0d9488);" +
    "box-shadow:0 4px 14px rgba(13,148,136,.45);animation:shBounce 1.4s ease-in-out infinite;opacity:.92;transition:opacity .2s;padding:0}" +
    ".sh-arrow:hover{opacity:1;animation-play-state:paused}" +
    ".sh-arrow svg{width:55%;height:55%}" +
    ".sh-arrow.sh-page{width:38px;height:38px;bottom:18px;right:18px}" +
    ".sh-arrow.sh-el{width:26px;height:26px}" +
    "@media (prefers-reduced-motion:reduce){.sh-arrow{animation:none}}";
  var SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>';
  var MIN_H = 90, GAP = 6, tracked = [], pageBtn = null, raf = 0, scanT = 0;

  function mk(cls, title) {
    var b = document.createElement("button");
    b.type = "button"; b.className = "sh-arrow " + cls; b.title = title;
    b.setAttribute("aria-label", title); b.innerHTML = SVG;
    document.body.appendChild(b); return b;
  }
  function isScrollable(el) {
    if (el.hasAttribute("data-no-scroll-hint") || el.closest("[data-no-scroll-hint]")) return false;
    if (el.clientHeight < MIN_H || el.scrollHeight - el.clientHeight < 12) return false;
    var oy = getComputedStyle(el).overflowY;
    return oy === "auto" || oy === "scroll";
  }
  function scan() {
    var all = document.body.getElementsByTagName("*"), seen = [];
    for (var i = 0; i < all.length; i++) {
      var el = all[i], tag = el.tagName;
      if (tag === "TEXTAREA" || tag === "SELECT" || tag === "svg" || el.classList.contains("sh-arrow")) continue;
      if (el.className && typeof el.className === "string" && el.className.indexOf("leaflet-") !== -1) continue;
      if (isScrollable(el)) seen.push(el);
    }
    // drop entries no longer scrollable
    tracked = tracked.filter(function (t) {
      if (seen.indexOf(t.el) === -1) { t.btn.remove(); return false; } return true;
    });
    seen.forEach(function (el) {
      for (var j = 0; j < tracked.length; j++) if (tracked[j].el === el) return;
      var btn = mk("sh-el", "Scroll down");
      btn.addEventListener("click", function () { el.scrollBy({ top: el.clientHeight * 0.8, behavior: "smooth" }); });
      el.addEventListener("scroll", schedule, { passive: true });
      tracked.push({ el: el, btn: btn });
    });
    schedule();
  }
  function update() {
    raf = 0;
    var vh = window.innerHeight, vw = window.innerWidth;
    var de = document.scrollingElement || document.documentElement;
    var pageMore = de.scrollHeight - (window.scrollY + vh) > 24 && getComputedStyle(document.body).overflowY !== "hidden";
    pageBtn.style.display = pageMore ? "flex" : "none";

    tracked.forEach(function (t) {
      var el = t.el, b = t.btn, show = false;
      if (el.isConnected && el.offsetParent !== null && el.scrollHeight - el.scrollTop - el.clientHeight > 12) {
        var r = el.getBoundingClientRect();
        var y = Math.min(r.bottom, vh) - 26 - GAP, x = Math.min(r.right, vw) - 26 - 12;
        if (r.bottom > 40 && r.top < vh - 40 && x > r.left && y > r.top) {
          // only show if this box is actually visible at that spot (not under a modal)
          var probe = document.elementFromPoint(Math.max(1, r.left + 6), Math.max(1, Math.min(y + 13, vh - 2)));
          if (probe && (el === probe || el.contains(probe))) {
            show = true; b.style.left = x + "px"; b.style.top = y + "px";
          }
        }
      }
      b.style.display = show ? "flex" : "none";
      if (show && y > vh - 90 && x > vw - 110) pageMore = false;
    });
    pageBtn.style.display = pageMore ? "flex" : "none";
  }
  function schedule() { if (!raf) raf = requestAnimationFrame(update); }
  function scheduleScan() { clearTimeout(scanT); scanT = setTimeout(scan, 250); }

  function init() {
    var st = document.createElement("style"); st.textContent = CSS; document.head.appendChild(st);
    pageBtn = mk("sh-page", "More below — scroll down");
    pageBtn.addEventListener("click", function () { window.scrollBy({ top: window.innerHeight * 0.8, behavior: "smooth" }); });
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", scheduleScan);
    document.addEventListener("scroll", schedule, { passive: true, capture: true });
    new MutationObserver(function (muts) {
      for (var i = 0; i < muts.length; i++) {
        var n = muts[i].target;
        if (n.nodeType !== 1 || n.classList.contains("sh-arrow")) continue;
        if (n.closest && n.closest(".leaflet-container")) continue;
        scheduleScan(); return;
      }
    }).observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["style", "class"] });
    scan();
    setTimeout(scan, 1200); // late-loading content (maps, fetches)
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
