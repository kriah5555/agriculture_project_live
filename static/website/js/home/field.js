/*
 * Homepage: "Where SoiLenz works today" globe (#field, design: EarthDeployments)
 * and the farmer impact photo wall (#growers, design: FarmerImpactWall).
 * Markup: templates/website/partials/home/_field.html, _growers.html.
 */
(function () {
  "use strict";

  var EASE = "cubic-bezier(0.22, 1, 0.36, 1)";
  var clamp01 = function (v) { return v < 0 ? 0 : v > 1 ? 1 : v; };

  /** scroll progress of an element, like Motion's useScroll({ target, offset }) */
  function progress(el, mode) {
    var r = el.getBoundingClientRect();
    var vh = window.innerHeight;
    if (mode === "pinned") {
      // offset ["start start", "end end"]
      var span = r.height - vh;
      return span > 0 ? clamp01(-r.top / span) : r.top <= 0 ? 1 : 0;
    }
    // offset ["start end", "end start"]
    return clamp01((vh - r.top) / (r.height + vh));
  }

  /* ======================= #field — deployment globe ======================= */
  function initField() {
    var section = document.getElementById("field");
    if (!section) return;
    var canvas = section.querySelector("[data-globe]");
    var hint = section.querySelector("[data-globe-hint]");
    var noGL = section.querySelector("[data-globe-nogl]");
    var cards = section.querySelector("[data-field-cards]");
    var line = section.querySelector("[data-field-line]");
    var buttons = Array.prototype.slice.call(section.querySelectorAll("[data-site]"));
    var sites = buttons.map(function (b) {
      return {
        id: b.getAttribute("data-site"),
        name: b.getAttribute("data-name"),
        region: b.getAttribute("data-region"),
        line: b.getAttribute("data-line"),
        photo: b.getAttribute("data-photo"),
        lat: parseFloat(b.getAttribute("data-lat")),
        lng: parseFloat(b.getAttribute("data-lng")),
        btn: b,
      };
    });
    var byId = {};
    sites.forEach(function (s) { byId[s.id] = s; });

    var globe = null;
    var activeId = null;
    var interactive = false;
    var shownCardId = null;
    var cardBusy = false;

    try {
      if (!window.ArkaGlobe) throw new Error("globe bundle missing");
      globe = window.ArkaGlobe.createGlobe(canvas, sites.map(function (s) { return { id: s.id, lat: s.lat, lng: s.lng }; }));
    } catch (e) {
      globe = null;
      noGL.hidden = false;
    }

    if (globe) {
      globe.resize(canvas.clientWidth, canvas.clientHeight);
      globe.onPick(function (id) { setActive(id); });
      if ("ResizeObserver" in window) {
        new ResizeObserver(function () { globe.resize(canvas.clientWidth, canvas.clientHeight); }).observe(canvas);
      } else {
        window.addEventListener("resize", function () { globe.resize(canvas.clientWidth, canvas.clientHeight); });
      }
      if ("IntersectionObserver" in window) {
        new IntersectionObserver(function (en) { globe.setActive(en[0].isIntersecting); }, { rootMargin: "200px" }).observe(section);
      }
    }

    /* ---- detail card (AnimatePresence mode="wait": old exits, then new enters) ---- */
    function buildCard(s) {
      var el = document.createElement("div");
      el.className = "ak-field-card flex gap-6";
      var photo = "";
      if (s.photo) {
        photo = '<div class="relative h-[200px] w-[170px] shrink-0 overflow-hidden rounded-[18px]">' +
          '<img alt="" decoding="async" class="object-cover" style="position:absolute;height:100%;width:100%;inset:0;color:transparent"></div>';
      }
      el.innerHTML = photo +
        '<div><p class="font-mono text-xs uppercase tracking-[0.18em] text-botanical"></p>' +
        '<p class="display mt-2 text-4xl text-ivory"></p>' +
        '<p class="mt-3 max-w-[26ch] text-[15px] leading-relaxed text-ivory/85"></p></div>';
      var img = el.querySelector("img");
      if (img) { img.src = s.photo; img.alt = "ArkaShine field work — " + s.region; }
      var ps = el.querySelectorAll("div > p");
      ps[0].textContent = s.region;
      ps[1].textContent = s.name;
      ps[2].textContent = s.line;
      return el;
    }

    function syncCard() {
      var want = interactive && activeId ? activeId : null;
      if (cardBusy || want === shownCardId) return;
      var old = cards.firstElementChild;
      if (old) {
        cardBusy = true;
        old.classList.remove("is-in");
        old.classList.add("is-out");
        setTimeout(function () {
          old.remove();
          shownCardId = null;
          cardBusy = false;
          syncCard();
        }, Arka.reduceMotion ? 0 : 500);
        return;
      }
      shownCardId = want;
      if (!want) return;
      var el = buildCard(byId[want]);
      cards.appendChild(el);
      el.getBoundingClientRect();
      requestAnimationFrame(function () { el.classList.add("is-in"); });
    }

    var ON_BTN = ["text-ivory"], OFF_BTN = ["text-ivory/75", "hover:text-ivory/80"];
    var ON_DOT = ["scale-150", "bg-botanical", "shadow-[0_0_10px_3px_rgba(140,191,95,0.6)]"], OFF_DOT = ["bg-ivory/30"];
    function render() {
      sites.forEach(function (s) {
        var on = s.id === activeId && interactive;
        var dot = s.btn.firstElementChild;
        s.btn.disabled = !interactive;
        s.btn.setAttribute("aria-pressed", String(on));
        ON_BTN.forEach(function (c) { s.btn.classList.toggle(c, on); });
        OFF_BTN.forEach(function (c) { s.btn.classList.toggle(c, !on); });
        ON_DOT.forEach(function (c) { dot.classList.toggle(c, on); });
        OFF_DOT.forEach(function (c) { dot.classList.toggle(c, !on); });
      });
      hint.classList.toggle("opacity-100", interactive);
      hint.classList.toggle("opacity-0", !interactive);
      canvas.classList.toggle("cursor-grab", interactive);
      canvas.classList.toggle("active:cursor-grabbing", interactive);
      var active = interactive && activeId ? byId[activeId] : null;
      line.hidden = !active;
      if (active) {
        line.querySelector("[data-field-line-name]").textContent = active.name;
        line.querySelector("[data-field-line-text]").textContent = active.line;
      }
      if (globe) globe.focus(interactive ? activeId : null);
      syncCard();
    }

    function setActive(id) {
      if (id === activeId) return;
      activeId = id;
      render();
    }

    buttons.forEach(function (b) {
      b.addEventListener("click", function () { if (interactive) setActive(b.getAttribute("data-site")); });
    });

    function onScroll() {
      var intro = progress(section, "pinned") / 0.75;
      if (globe) globe.setIntro(intro);
      var ok = intro > 0.86;
      if (ok === interactive) return;
      interactive = ok;
      if (ok && !activeId) activeId = "karnataka";
      render();
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    onScroll();
    render();
  }

  /* ======================= #growers — farmer impact wall ======================= */
  var PIN_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-map-pin h-4 w-4 shrink-0 text-botanical" aria-hidden="true"><path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"></path><circle cx="12" cy="10" r="3"></circle></svg>';

  function initGrowers() {
    var section = document.getElementById("growers");
    if (!section) return;
    var wall = section.querySelector("[data-wall]");
    var cols = section.querySelectorAll("[data-wall-col]");

    /* scroll parallax on the columns: A 4% → -18%, B -16% → 6% */
    var parallax = function () {
      var p = progress(section);
      cols.forEach(function (c) {
        var y = c.getAttribute("data-wall-col") === "b" ? -16 + 22 * p : 4 - 22 * p;
        c.style.transform = "translateY(" + y.toFixed(3) + "%)";
      });
    };
    window.addEventListener("scroll", parallax, { passive: true });
    window.addEventListener("resize", parallax);
    parallax();

    /* labels: second (aria-hidden) copy of each tile has an empty alt — map by src */
    var labels = {};
    var PREFIX = "ArkaShine field photo: ";
    wall.querySelectorAll("img").forEach(function (img) {
      var alt = img.getAttribute("alt") || "";
      if (alt.indexOf(PREFIX) === 0) labels[img.getAttribute("src")] = alt.slice(PREFIX.length);
    });

    /* hover preview: lifts out of the wall, follows the cursor, sinks back on its own */
    var px = { x: 0, v: 0, t: 0 }, py = { x: 0, v: 0, t: 0 };
    var side = "right";
    var previews = []; // live (entering/visible/exiting) preview elements
    var current = null; // { el, src }
    var lastSrc = null, showTimer = null, hideTimer = null;
    var raf = 0, lastT = 0;

    function step(sp, dt) { // spring: stiffness 160, damping 24, mass 1
      var f = -160 * (sp.x - sp.t) - 24 * sp.v;
      sp.v += f * dt;
      sp.x += sp.v * dt;
    }
    function tick(t) {
      var dt = Math.min((t - lastT) / 1000 || 0.016, 0.05);
      lastT = t;
      for (var i = 0; i < 4; i++) { step(px, dt / 4); step(py, dt / 4); }
      previews.forEach(function (el) { el.style.transform = "translate3d(" + px.x.toFixed(1) + "px," + py.x.toFixed(1) + "px,0)"; });
      var settled = Math.abs(px.x - px.t) < 0.3 && Math.abs(py.x - py.t) < 0.3 && Math.abs(px.v) < 0.3 && Math.abs(py.v) < 0.3;
      raf = previews.length && !settled ? requestAnimationFrame(tick) : 0;
    }
    function kick() { if (!raf) { lastT = performance.now(); raf = requestAnimationFrame(tick); } }

    function highlight(src, on) {
      if (!src) return;
      wall.querySelectorAll("img").forEach(function (img) {
        if (img.getAttribute("src") !== src) return;
        var tile = img.parentElement;
        tile.classList.toggle("ring-2", on);
        tile.classList.toggle("ring-botanical", on);
      });
    }

    function clearTimers() { clearTimeout(showTimer); clearTimeout(hideTimer); }

    function hide() {
      if (!current) return;
      var c = current;
      current = null;
      highlight(c.src, false);
      c.el.classList.add("is-out");
      setTimeout(function () {
        c.el.remove();
        previews = previews.filter(function (x) { return x !== c.el; });
      }, Arka.reduceMotion ? 0 : 560);
    }

    function show(img) {
      hide();
      var src = img.getAttribute("src");
      var label = labels[src] || "";
      var tile = img.parentElement;
      var ar = (tile.style.aspectRatio || "1 / 1").split("/");
      var ratio = Math.max(parseFloat(ar[0]) / parseFloat(ar[1] || 1) || 1, 0.8);

      var el = document.createElement("div");
      el.className = "ak-preview pointer-events-none fixed left-0 top-0 z-50 w-[min(460px,80vw)] [perspective:900px]";
      el.innerHTML =
        '<div class="ak-preview-card ak-from-' + side + '">' +
        '<div class="overflow-hidden rounded-2xl border border-white/20 bg-forest-deep shadow-[0_30px_80px_rgba(0,0,0,0.75)]">' +
        '<div class="relative w-full bg-black" style="aspect-ratio:' + ratio + '"><img alt="" decoding="async" class="object-contain" style="position:absolute;height:100%;width:100%;inset:0;color:transparent"></div>' +
        '<div class="flex items-center gap-2 px-4 py-3">' + PIN_SVG + '<span class="truncate font-mono text-xs uppercase tracking-[0.14em] text-ivory"></span></div>' +
        '<div class="ak-preview-bar h-0.5 bg-botanical"></div></div></div>';
      var pimg = el.querySelector("img");
      pimg.src = src;
      pimg.alt = label;
      el.querySelector("span.truncate").textContent = label;
      el.style.transform = "translate3d(" + px.x + "px," + py.x + "px,0)";
      section.appendChild(el);
      previews.push(el);
      current = { el: el, src: src };
      highlight(src, true);
      el.getBoundingClientRect();
      requestAnimationFrame(function () { el.classList.add("is-in"); });
      kick();
      hideTimer = setTimeout(hide, 2600);
    }

    wall.addEventListener("pointermove", function (e) {
      var vw = window.innerWidth, vh = window.innerHeight;
      var cardW = Math.min(460, vw * 0.8);
      side = e.clientX > vw / 2 ? "left" : "right";
      var x = side === "right" ? e.clientX + 28 : e.clientX - cardW - 28;
      px.t = Math.max(12, Math.min(vw - cardW - 12, x));
      py.t = Math.max(12, Math.min(vh - cardW * 0.8 - 12, e.clientY - cardW * 0.35));
      if (!previews.length) { px.x = px.t; py.x = py.t; } // first card appears at the cursor
      kick();

      var tile = e.target.closest && e.target.closest(".group");
      var img = tile && wall.contains(tile) ? tile.querySelector("img") : null;
      if (!img) return;
      var src = img.getAttribute("src");
      if (src === lastSrc) return;
      lastSrc = src;
      clearTimers();
      showTimer = setTimeout(function () { show(img); }, 90);
    });
    wall.addEventListener("pointerleave", function () {
      clearTimers();
      lastSrc = null;
      hide();
    });
  }

  Arka.onReady(function () {
    initField();
    initGrowers();
  });
})();
