/* Homepage product sections — replaces the design's ProductReveal / SoilenzStage,
 * SensorShowcase / FocusImage, AppShowcase and HowItWorksVideo (React + Motion).
 * Partials: templates/website/partials/home/_soillenz.html, _ph_ec.html, _app.html, _how_video.html
 */
(function () {
  "use strict";

  var reduce = function () { return !!(window.Arka && window.Arka.reduceMotion); };
  var clamp = function (v, lo, hi) { return Math.max(lo, Math.min(hi, v)); };
  var swapClasses = function (el, off, on) {
    off.forEach(function (c) { el.classList.remove(c); });
    on.forEach(function (c) { el.classList.add(c); });
  };

  /**
   * useAutoCycle: advances every `ms` while ≥40% of `section` is in view, until the
   * user picks an item. `render(i, prev)` draws the state.
   */
  function autoCycle(section, count, ms, render) {
    var state = { index: 0, locked: false, inView: false, timer: null };
    var stop = function () { if (state.timer) { clearInterval(state.timer); state.timer = null; } };
    var sync = function () {
      stop();
      if (!state.inView || state.locked || reduce()) return;
      state.timer = setInterval(function () { set((state.index + 1) % count); }, ms);
    };
    var set = function (i) {
      if (i === state.index) return;
      var prev = state.index;
      state.index = i;
      render(i, prev);
    };
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (entries) {
        entries.forEach(function (e) { state.inView = e.isIntersecting && e.intersectionRatio >= 0.4; });
        sync();
      }, { threshold: [0, 0.4] }).observe(section);
    }
    return {
      pick: function (i) { state.locked = true; sync(); set(i); },
      get index() { return state.index; },
    };
  }

  /** AnimatePresence mode="wait"-style text swap on an .ak-swap element. */
  function swapText(el, text, outMs) {
    if (reduce()) { el.textContent = text; return; }
    clearTimeout(el._akT);
    el.classList.add("is-out");
    el._akT = setTimeout(function () {
      el.textContent = text;
      el.classList.remove("is-out");
      el.classList.add("is-pre");
      void el.offsetWidth;
      el.classList.remove("is-pre");
    }, outMs);
  }

  /** Scroll progress of `el` between two offsets, like Motion's useScroll. */
  function progress(el, startFn, endFn) {
    var r = el.getBoundingClientRect();
    var vh = window.innerHeight;
    var s = startFn(r, vh), e = endFn(r, vh);
    return e === s ? 0 : clamp(s / (s - e), 0, 1);
  }

  /* ---------------- SoiLenz 2.0 ---------------- */
  function initSoilenz() {
    var sec = document.querySelector("[data-soillenz]");
    if (!sec) return;
    var tabs = [].slice.call(sec.querySelectorAll("[data-sl-tab]"));
    var caption = sec.querySelector("[data-sl-caption]");
    var lift = sec.querySelector("[data-sl-lift]");
    var glow = sec.querySelector("[data-sl-glow]");
    var stage = sec.querySelector("[data-sl-stage]");
    var tilt = sec.querySelector("[data-sl-tilt]");
    var zoom = sec.querySelector("[data-sl-zoom]");

    var ON = { no: ["text-botanical"], title: ["text-ivory"], dot: ["bg-botanical", "shadow-[0_0_12px_3px_rgba(140,191,95,0.55)]"] };
    var OFF = { no: ["text-ivory/70"], title: ["text-ivory/80", "group-hover:text-ivory/80"], dot: ["bg-ivory/15"] };

    var render = function (i) {
      tabs.forEach(function (t, k) {
        var on = k === i;
        t.setAttribute("aria-selected", String(on));
        var a = on ? OFF : ON, b = on ? ON : OFF;
        swapClasses(t.querySelector("[data-no]"), a.no, b.no);
        swapClasses(t.querySelector("[data-title]"), a.title, b.title);
        swapClasses(t.querySelector("[data-dot]"), a.dot, b.dot);
      });
      var t = tabs[i];
      swapText(caption, t.querySelector("[data-no]").textContent + " · " + t.querySelector("[data-title]").textContent, 400);
    };
    var cycle = autoCycle(sec, tabs.length, 4800, render);
    tabs.forEach(function (t, k) {
      t.addEventListener("click", function () { cycle.pick(k); });
      t.addEventListener("mouseenter", function () { cycle.pick(k); });
    });

    // scroll: card lifts 90px → 0 and the studio glow fades in as the section arrives;
    // the photo pushes in 1.08 → 1.02 → 1.06 across the stage's pass through the viewport.
    var ticking = false;
    var update = function () {
      ticking = false;
      var p = progress(sec, function (r, vh) { return r.top - vh; }, function (r) { return r.top; }); // ["start end","start start"]
      if (reduce()) { lift.style.transform = "none"; glow.style.opacity = "1"; return; }
      lift.style.transform = "translateY(" + (90 * (1 - p)).toFixed(2) + "px)";
      glow.style.opacity = clamp((p - 0.2) / 0.8, 0, 1).toFixed(3);
      var q = progress(stage, function (r, vh) { return r.top - vh; }, function (r) { return r.bottom; }); // ["start end","end start"]
      var sc = q < 0.5 ? 1.08 - 0.06 * (q / 0.5) : 1.02 + 0.04 * ((q - 0.5) / 0.5);
      zoom.style.transform = "scale(" + sc.toFixed(4) + ")";
    };
    var onScroll = function () { if (!ticking) { ticking = true; requestAnimationFrame(update); } };
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    update();

    // pointer: small 3D tilt
    if (!reduce()) {
      stage.addEventListener("pointermove", function (e) {
        var r = stage.getBoundingClientRect();
        var mx = (e.clientX - r.left) / r.width - 0.5;
        var my = (e.clientY - r.top) / r.height - 0.5;
        tilt.style.transform = "rotateX(" + (-6 * my).toFixed(2) + "deg) rotateY(" + (8 * mx).toFixed(2) + "deg)";
      });
      stage.addEventListener("pointerleave", function () { tilt.style.transform = ""; });
    }
  }

  /* ---------------- pH & EC capsule ---------------- */
  function initPhEc() {
    var sec = document.querySelector("[data-phec]");
    if (!sec) return;
    var tabs = [].slice.call(sec.querySelectorAll("[data-ph-tab]"));
    var bar = sec.querySelector("[data-ph-tabs]");
    var underline = sec.querySelector("[data-ph-underline]");
    var img = sec.querySelector("[data-ph-img]");
    var marker = sec.querySelector("[data-ph-marker]");
    var line = sec.querySelector("[data-ph-line]");

    // FocusImage for a frame with the image's own aspect: image box = frame.
    var applyFocus = function (str) {
      var f = str.split(",").map(Number), x = f[0], y = f[1], s = f[2];
      var tx = clamp((50 - x) * s, 50 - 50 * s, 50 * s - 50);
      var ty = clamp((50 - y) * s, 50 - 50 * s, 50 * s - 50);
      img.style.transform = "translateX(" + tx.toFixed(2) + "%) translateY(" + ty.toFixed(2) + "%) scale(" + s + ")";
      marker.style.left = (50 + (x - 50) * s + tx).toFixed(2) + "%";
      marker.style.top = (50 + (y - 50) * s + ty).toFixed(2) + "%";
      marker.classList.remove("is-anim");
      void marker.offsetWidth;
      if (!reduce()) marker.classList.add("is-anim");
    };
    var placeUnderline = function () {
      var t = tabs[cycle ? cycle.index : 0];
      underline.style.left = t.offsetLeft + "px";
      underline.style.top = t.offsetTop + t.offsetHeight - 1 + "px";
      underline.style.width = t.offsetWidth + "px";
    };
    var render = function (i) {
      tabs.forEach(function (t, k) {
        var on = k === i;
        t.setAttribute("aria-selected", String(on));
        swapClasses(t, on ? ["text-ink/75", "hover:text-ink/75"] : ["text-forest"], on ? ["text-forest"] : ["text-ink/75", "hover:text-ink/75"]);
      });
      placeUnderline();
      applyFocus(tabs[i].getAttribute("data-focus"));
      swapText(line, tabs[i].getAttribute("data-line"), 450);
    };
    var cycle = null;
    cycle = autoCycle(sec, tabs.length, 4200, render);
    tabs.forEach(function (t, k) { t.addEventListener("click", function () { cycle.pick(k); }); });
    // first paint: no slide-in for the underline
    underline.style.transition = "none";
    placeUnderline();
    void underline.offsetWidth;
    underline.style.transition = "";
    window.addEventListener("resize", placeUnderline);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(placeUnderline);
    // first focus marker pulse once the photo is on screen
    if ("IntersectionObserver" in window && !reduce()) {
      var io = new IntersectionObserver(function (es) {
        if (es[0].isIntersecting) { io.disconnect(); if (cycle.index === 0) applyFocus(tabs[0].getAttribute("data-focus")); }
      }, { threshold: 0.3 });
      io.observe(img.parentElement);
    }
  }

  /* ---------------- Soil Partner app ---------------- */
  function initApp() {
    var sec = document.querySelector("[data-appshow]");
    if (!sec) return;
    var tabs = [].slice.call(sec.querySelectorAll("[data-app-tab]"));
    var screens = [].slice.call(sec.querySelectorAll("[data-app-screen]"));
    var count = sec.querySelector("[data-app-count]");
    var phone = sec.querySelector("[data-app-phone]");

    var render = function (i, prev) {
      tabs.forEach(function (t, k) {
        var on = k === i;
        t.setAttribute("aria-selected", String(on));
        t.querySelector("[data-bar]").classList.toggle("is-on", on);
        swapClasses(t.querySelector("[data-title]"), on ? ["text-ink/70", "group-hover:text-ink/85"] : ["text-forest"], on ? ["text-forest"] : ["text-ink/70", "group-hover:text-ink/85"]);
      });
      count.textContent = (i + 1 < 10 ? "0" : "") + (i + 1);
      var next = screens[i], old = screens[prev];
      screens.forEach(function (s) { if (s !== next && s !== old) { s.hidden = true; s.classList.remove("is-leaving", "is-pre"); } });
      if (reduce()) { old.hidden = true; next.hidden = false; return; }
      clearTimeout(old._akT);
      old.classList.remove("is-pre");
      old.classList.add("is-leaving");
      old._akT = setTimeout(function () { old.hidden = true; old.classList.remove("is-leaving"); }, 560);
      clearTimeout(next._akT);
      next.classList.remove("is-leaving");
      next.classList.add("is-pre");
      next.hidden = false;
      void next.offsetWidth;
      next.classList.remove("is-pre");
    };
    var cycle = autoCycle(sec, tabs.length, 5200, render);
    tabs.forEach(function (t, k) { t.addEventListener("click", function () { cycle.pick(k); }); });

    // phone rises in once 30% is visible
    if (!reduce() && "IntersectionObserver" in window && phone.getBoundingClientRect().top > window.innerHeight * 0.7) {
      phone.classList.add("ak-pre");
      var io = new IntersectionObserver(function (es) {
        if (!es[0].isIntersecting) return;
        io.disconnect();
        phone.classList.add("ak-in");
        void phone.offsetWidth;
        phone.classList.remove("ak-pre");
      }, { threshold: 0.3 });
      io.observe(phone);
    }
  }

  /* ---------------- four-steps film ---------------- */
  function initHowVideo() {
    var v = document.querySelector("[data-how-video]");
    if (!v) return;
    v.muted = true; // muted must be a property for autoplay to be allowed everywhere
    v.playsInline = true;
    if (!("IntersectionObserver" in window)) { v.play().catch(function () {}); return; }
    new IntersectionObserver(function (es) {
      if (es[0].isIntersecting) v.play().catch(function () {});
      else v.pause();
    }, { threshold: 0.25 }).observe(v);
  }

  window.Arka.onReady(function () {
    initSoilenz();
    initPhEc();
    initApp();
    initHowVideo();
  });
})();
