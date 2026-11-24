/*
 * #solutions — Who we work with (design: EcosystemRibbon in src/components/cinema/StorySections.tsx)
 *  - the active audience row follows the scroll position through the section,
 *    and hover / click / Enter on a row makes it active
 *  - the photo card shows the active audience; the CSR gallery rotates every 2400ms
 */
(function () {
  "use strict";

  var ROW_ON = ["opacity-100"], ROW_OFF = ["opacity-45", "hover:opacity-85"];
  var ICON_ON = ["text-botanical"], ICON_OFF = ["text-ivory/70", "group-hover:text-ivory/85"];
  var NAME_ON = ["text-ivory", "translate-x-1"], NAME_OFF = ["text-ivory/85", "group-hover:text-ivory"];
  var PANEL_ON = ["opacity-100", "scale-100"], PANEL_OFF = ["opacity-0", "scale-105", "pointer-events-none"];
  var THUMB_ON = ["-translate-y-1.5", "border-botanical", "shadow-lg"], THUMB_OFF = ["border-white/30", "opacity-60"];

  function swap(el, on, onCls, offCls) {
    if (!el) return;
    (on ? offCls : onCls).forEach(function (c) { el.classList.remove(c); });
    (on ? onCls : offCls).forEach(function (c) { el.classList.add(c); });
  }
  /** show/hide and replay the element's entrance animation */
  function reveal(el, on) {
    if (!el) return;
    if (!on) { el.hidden = true; return; }
    if (!el.hidden) return;
    el.hidden = false;
    el.classList.remove("ak-sol-enter");
    el.offsetWidth;
    el.classList.add("ak-sol-enter");
  }

  Arka.onReady(function () {
    var section = document.querySelector("[data-sol]");
    if (!section) return;
    var rows = Array.prototype.slice.call(section.querySelectorAll("[data-sol-row]"));
    var panels = Array.prototype.slice.call(section.querySelectorAll("[data-sol-panel]"));
    var n = rows.length;
    var active = -1;
    var galleryTimer = null;
    var galleryIdx = 0;

    function q(sel) { return section.querySelector(sel); }

    /* ---- CSR gallery ---- */
    function showGallery(panel, idx) {
      var slides = panel.querySelectorAll("[data-sol-g]");
      var thumbs = panel.querySelectorAll("[data-sol-thumb]");
      var k = idx % slides.length;
      Array.prototype.forEach.call(slides, function (g, gi) {
        if (gi === k) {
          // start from the entering pose (no transition), then animate in
          g.classList.add("ak-sol-g-reset");
          g.classList.remove("is-off", "is-on");
          g.offsetWidth;
          g.classList.remove("ak-sol-g-reset");
          g.classList.add("is-on");
        } else if (g.classList.contains("is-on")) {
          g.classList.remove("is-on");
          g.classList.add("is-off");
        }
      });
      Array.prototype.forEach.call(thumbs, function (t, ti) { swap(t, ti === k, THUMB_ON, THUMB_OFF); });
    }
    function syncGallery() {
      var panel = panels[active];
      var hasGallery = panel && panel.querySelector("[data-sol-g]");
      if (hasGallery && !galleryTimer && !Arka.reduceMotion) {
        galleryTimer = setInterval(function () { galleryIdx += 1; showGallery(panels[active], galleryIdx); }, 2400);
      } else if (!hasGallery && galleryTimer) {
        clearInterval(galleryTimer);
        galleryTimer = null;
      }
    }

    function setActive(i) {
      if (i === active) return;
      active = i;
      rows.forEach(function (row, idx) {
        var on = idx === i;
        row.setAttribute("aria-pressed", String(on));
        swap(row, on, ROW_ON, ROW_OFF);
        swap(row.querySelector("[data-sol-icon]"), on, ICON_ON, ICON_OFF);
        swap(row.querySelector("[data-sol-name]"), on, NAME_ON, NAME_OFF);
        reveal(row.querySelector("[data-sol-detail]"), on);
        reveal(row.querySelector("[data-sol-bar]"), on);
        reveal(row.querySelector("[data-sol-line]"), on);
        var dot = row.querySelector("[data-sol-dot]");
        if (dot) dot.hidden = on;
      });
      panels.forEach(function (p, idx) {
        var on = idx === i;
        swap(p, on, PANEL_ON, PANEL_OFF);
        if (on) { p.removeAttribute("aria-hidden"); p.removeAttribute("tabindex"); }
        else { p.setAttribute("aria-hidden", "true"); p.setAttribute("tabindex", "-1"); }
      });
      section.querySelectorAll("[data-sol-stats]").forEach(function (s) {
        reveal(s, Number(s.getAttribute("data-sol-stats")) === i);
      });
      section.querySelectorAll("[data-sol-caption]").forEach(function (c) {
        c.hidden = Number(c.getAttribute("data-sol-caption")) !== i;
      });
      syncGallery();
    }

    rows.forEach(function (row, idx) {
      row.addEventListener("click", function (e) { if (!e.target.closest("a")) setActive(idx); });
      row.addEventListener("mouseenter", function () { setActive(idx); });
      row.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setActive(idx); }
      });
    });

    /* as the page scrolls through the section, step through the audiences (same maths as the design) */
    function onScroll() {
      var rect = section.getBoundingClientRect();
      var h = window.innerHeight;
      var progress = Math.min(Math.max((h * 0.65 - rect.top) / (rect.height + h * 0.2), 0), 0.999);
      setActive(Math.min(Math.floor(progress * n), n - 1));
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    section.classList.add("ak-sol-live");
    onScroll();
  });
})();
