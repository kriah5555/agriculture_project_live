/*
 * #advisory — Advisory reports (design: src/components/home/AdvisoryReports.tsx)
 *  - fanned 3D report stack that deals itself every 2400ms while in view;
 *    hovering fans the pages out (hover a page to lift it), click opens the reader
 *  - reader dialog [data-modal="report"] with prev / next / ← → / Esc
 *  - score gauge stroke, parameter bars, count-up numbers when scrolled into view
 */
(function () {
  "use strict";

  var EASE_OUT = function (t) { return 1 - Math.pow(1 - t, 4); }; // ≈ cubic-bezier(0.22, 1, 0.36, 1)

  /** observe once: fn(el) when `amount` of el is visible */
  function onceInView(els, amount, fn) {
    if (!("IntersectionObserver" in window)) { els.forEach(fn); return; }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        io.unobserve(en.target);
        fn(en.target);
      });
    }, { threshold: amount });
    els.forEach(function (el) { io.observe(el); });
  }

  /* ---------------- count-up numbers ---------------- */
  function fmt(v, dec, suffix) {
    return v.toLocaleString("en-IN", { minimumFractionDigits: dec, maximumFractionDigits: dec }) + suffix;
  }
  function initCounts(root, reduce) {
    var els = Array.prototype.slice.call(root.querySelectorAll("[data-count]"));
    els.forEach(function (el) {
      var to = parseFloat(el.getAttribute("data-count"));
      var dec = Number(el.getAttribute("data-dec") || 0);
      var suf = el.getAttribute("data-suffix") || "";
      el.textContent = fmt(reduce ? to : 0, dec, suf);
    });
    if (reduce) return;
    onceInView(els, 0.6, function (el) {
      var to = parseFloat(el.getAttribute("data-count"));
      var dec = Number(el.getAttribute("data-dec") || 0);
      var suf = el.getAttribute("data-suffix") || "";
      var t0 = performance.now();
      var tick = function (now) {
        var p = Math.min(1, (now - t0) / 1600);
        el.textContent = fmt(to * EASE_OUT(p), dec, suf);
        if (p < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });
  }

  /* ---------------- gauge, bars, step line ---------------- */
  function initMeters(root, reduce) {
    var gauge = root.querySelector("[data-adv-gauge]");
    if (gauge) {
      var c = Math.PI * 46;
      var end = c * (1 - Number(gauge.getAttribute("data-score")) / 100);
      gauge.setAttribute("stroke-dasharray", String(c));
      gauge.style.strokeDashoffset = (reduce ? end : c) + "px";
      if (!reduce) onceInView([gauge], 0.1, function () {
        gauge.classList.add("ak-adv-gauge-go");
        requestAnimationFrame(function () { gauge.style.strokeDashoffset = end + "px"; });
      });
    }
    var bars = Array.prototype.slice.call(root.querySelectorAll("[data-adv-bar]"));
    if (!reduce) {
      bars.forEach(function (b) { b.style.width = "0%"; });
      onceInView(bars, 0.1, function (b) {
        b.classList.add("ak-adv-bar-go");
        requestAnimationFrame(function () { b.style.width = b.getAttribute("data-w"); });
      });
    }
    var line = root.querySelector("[data-adv-line]");
    if (line && !reduce) {
      line.classList.add("ak-adv-line-start");
      onceInView([line], 0.1, function () { line.classList.remove("ak-adv-line-start"); });
    }
  }

  /* ---------------- report stack ---------------- */
  function initStack(root, reduce, openReader) {
    var stack = root.querySelector("[data-adv-stack]");
    if (!stack) return;
    var pages = Array.prototype.slice.call(stack.querySelectorAll("[data-adv-page]"));
    var label = stack.querySelector("[data-adv-label]");
    var n = pages.length;
    var titles = pages.map(function (b) { return (b.getAttribute("aria-label") || "").replace(/^.*?:\s*/, ""); });
    var top = 0, fan = false, inView = false, timer = null, hovered = -1;

    var sweep = document.createElement("span");
    sweep.className = "ak-adv-sweep pointer-events-none absolute inset-y-0 w-1/3 -skew-x-12 bg-gradient-to-r from-transparent via-white/50 to-transparent";
    sweep.setAttribute("aria-hidden", "true");

    function pose(i) {
      var t;
      if (fan) {
        var fx = (i - (n - 1) / 2) * 26;
        t = { x: fx * 0.7, y: Math.abs(fx) * 0.4, rz: fx * 0.28, ry: 0, s: 0.76, o: 1, z: i };
        if (i === hovered) { t.y = -36; t.s = 0.8; t.rz = 0; t.z = 50; }
      } else {
        var d = (i - top + n) % n; // 0 = front
        t = { x: d * 10, y: d * -10, rz: d === 0 ? -2 : d * 1.6, ry: d === 0 ? -8 : -14, s: 1 - d * 0.03, o: d > 4 ? 0 : 1, z: n - d };
      }
      return t;
    }
    function render() {
      pages.forEach(function (b, i) {
        var t = pose(i);
        b.style.zIndex = t.z;
        b.style.opacity = t.o;
        b.style.transform = "translateX(" + t.x + "px) translateY(" + t.y + "px) scale(" + t.s + ") rotateY(" + t.ry + "deg) rotateZ(" + t.rz + "deg)";
      });
    }
    function setLabel(text) {
      if (!label || label.textContent === text) return;
      if (reduce) { label.textContent = text; return; }
      label.classList.add("ak-adv-label-out");
      setTimeout(function () {
        label.textContent = text;
        label.classList.remove("ak-adv-label-out");
        label.classList.add("ak-adv-label-in");
        label.offsetWidth; // restart from below
        label.classList.remove("ak-adv-label-in");
      }, 180);
    }
    function runSweep() {
      if (fan || reduce) { if (sweep.parentNode) sweep.parentNode.removeChild(sweep); return; }
      pages[top].appendChild(sweep);
      sweep.classList.remove("is-go");
      sweep.offsetWidth;
      sweep.classList.add("is-go");
    }
    function update(deal) {
      render();
      setLabel(fan ? "Click a page to read" : String(top + 1).padStart(2, "0") + " · " + titles[top]);
      if (deal) runSweep();
      else if (fan && sweep.parentNode) sweep.parentNode.removeChild(sweep);
    }
    function sync() {
      var run = inView && !fan && !reduce;
      if (run && !timer) timer = setInterval(function () { top = (top + 1) % n; update(true); }, 2400);
      if (!run && timer) { clearInterval(timer); timer = null; }
    }

    stack.addEventListener("mouseenter", function () { fan = true; update(false); sync(); });
    stack.addEventListener("mouseleave", function () { fan = false; hovered = -1; update(true); sync(); });
    pages.forEach(function (b, i) {
      b.addEventListener("mouseenter", function () { hovered = i; if (fan) render(); });
      b.addEventListener("mouseleave", function () { if (hovered === i) hovered = -1; if (fan) render(); });
      b.addEventListener("click", function () { openReader(i); });
    });

    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (entries) {
        inView = entries[entries.length - 1].isIntersecting;
        sync();
      }, { threshold: 0.35 }).observe(stack);
    }
    stack.classList.add("ak-adv-live");
    update(true);
  }

  /* ---------------- reader dialog ---------------- */
  function initReader(root) {
    var modal = document.querySelector("[data-adv-reader]");
    var srcs = Array.prototype.slice.call(root.querySelectorAll("[data-adv-page] img")).map(function (img) {
      return img.getAttribute("src");
    });
    if (!modal || !srcs.length) return function () {};
    var img = modal.querySelector("[data-adv-reader-img]");
    var sheet = modal.querySelector("[data-adv-sheet]");
    var prev = modal.querySelector("[data-adv-prev]");
    var next = modal.querySelector("[data-adv-next]");
    var page = 0;

    function show(i, animate) {
      page = Math.max(0, Math.min(srcs.length - 1, i));
      img.src = srcs[page];
      img.alt = "Sample advisory report, page " + (page + 1);
      prev.hidden = page === 0;
      next.hidden = page === srcs.length - 1;
      if (animate && !Arka.reduceMotion) {
        sheet.classList.remove("ak-adv-flip");
        sheet.offsetWidth;
        sheet.classList.add("ak-adv-flip");
      }
    }
    prev.addEventListener("click", function () { show(page - 1, true); });
    next.addEventListener("click", function () { show(page + 1, true); });
    document.addEventListener("keydown", function (e) {
      if (modal.hidden || !modal.classList.contains("is-open")) return;
      if (e.key === "ArrowRight") { e.preventDefault(); show(page + 1, true); }
      if (e.key === "ArrowLeft") { e.preventDefault(); show(page - 1, true); }
    });
    return function open(i) {
      show(i, false);
      Arka.openModal("report");
    };
  }

  Arka.onReady(function () {
    var root = document.getElementById("advisory");
    if (!root) return;
    var reduce = Arka.reduceMotion;
    var openReader = initReader(root);
    initStack(root, reduce, openReader);
    initMeters(root, reduce);
    initCounts(root, reduce);
  });
})();
