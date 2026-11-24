/*
 * "How we work" (design: HowWeWork.tsx).
 *  - desktop (#how-we-work, lg+): pinned photo story; scroll progress picks the active
 *    chapter (photo, journey bar, text, proof card); clicking a step scrolls to it.
 *  - mobile (#how-we-work-mobile): stacked chapters; each card plays when in view.
 *  - proof cards (_how_we_work_card.html): TerraMap year ticker, report page flipper,
 *    GeoLenz map rotator, consultation slot picker, entrance animations.
 */
(function () {
  "use strict";

  var YEARS = [2019, 2020, 2021, 2022, 2023, 2024, 2025];
  var PAGES = ["Soil health score", "14-parameter results", "Field grid heatmaps", "Fertiliser plan", "Crop suitability", "Dose per crop", "Organic & natural inputs", "Carbon impact"];
  var MAPS = ["Nitrogen layer", "N · P · K · pH maps", "Field mapping report"];
  var SEASONS = ["Kharif", "Rabi", "Zaid"];
  var DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  var SLOTS = ["10:00 AM", "12:00 PM", "3:00 PM", "5:00 PM"];

  var swap = function (el, off, on) {
    off.forEach(function (c) { el.classList.remove(c); });
    on.forEach(function (c) { el.classList.add(c); });
  };
  var pageSrc = function (i) {
    return window.ARKA_ASSET + "images/advisory/" + (i === 0 ? "report-p1-bhanu.webp" : "report-p" + (i + 1) + ".webp");
  };

  /* ------------------------------------------------------------------ */
  /* proof cards                                                          */
  /* ------------------------------------------------------------------ */

  /** Per-kind ticker: render(idx) draws state idx; period in ms; count = cycle length. */
  function tickerFor(card, kind) {
    if (kind === "geo") {
      var zones = card.querySelectorAll("[data-hww-zone]");
      var bars = card.querySelectorAll("[data-hww-ybar]");
      var year = card.querySelector("[data-hww-year]");
      return {
        period: 900, count: YEARS.length,
        render: function (y) {
          year.textContent = String(YEARS[y]);
          zones.forEach(function (z, i) { z.style.opacity = (y + i) % 3 === 0 ? "0.35" : "0.9"; });
          bars.forEach(function (b, i) { swap(b, i <= y ? ["bg-[#fff]/15"] : ["bg-[#8CBF5F]"], i <= y ? ["bg-[#8CBF5F]"] : ["bg-[#fff]/15"]); });
        },
      };
    }
    if (kind === "report") {
      var front = card.querySelector('[data-hww-page="0"]');
      var back = card.querySelector('[data-hww-page="1"]');
      var cap = card.querySelector("[data-hww-caption]");
      var preloaded = false;
      var set = function (img, i) {
        var src = pageSrc(i);
        if (img.getAttribute("src") !== src) img.setAttribute("src", src);
        img.alt = "AI advisory report page " + (i + 1) + ": " + PAGES[i];
      };
      return {
        period: 1600, count: PAGES.length,
        start: function () {
          if (preloaded) return;
          preloaded = true;
          PAGES.forEach(function (_, i) { var im = new Image(); im.src = pageSrc(i); });
        },
        render: function (p) {
          set(front, p);
          set(back, (p + 1) % PAGES.length);
          cap.textContent = PAGES[p];
        },
      };
    }
    if (kind === "geolenz") {
      var maps = card.querySelectorAll("[data-hww-map]");
      var mcap = card.querySelector("[data-hww-caption]");
      return {
        period: 2200, count: MAPS.length,
        render: function (m) {
          maps.forEach(function (el, i) {
            el.classList.toggle("is-on", i === m);
            if (i === m) el.removeAttribute("aria-hidden"); else el.setAttribute("aria-hidden", "true");
          });
          mcap.textContent = MAPS[m];
        },
      };
    }
    return null;
  }

  function initBook(card) {
    var sel = { season: 0, day: 1, slot: 0 };
    var label = card.querySelector("[data-hww-book-label]");
    var STYLE = {
      season: { on: ["border-[#8CBF5F]", "bg-[#8CBF5F]/15"], off: ["border-[#fff]/15", "hover:border-[#fff]/35"] },
      day: { on: ["bg-[#8CBF5F]", "text-[#06201e]"], off: ["bg-[#fff]/10", "text-[#fff]/85", "hover:bg-[#fff]/20"] },
      slot: { on: ["border-[#8CBF5F]", "bg-[#8CBF5F]/15", "font-semibold", "text-[#d9f99d]"], off: ["border-[#fff]/15", "text-[#fff]/80", "hover:border-[#fff]/35"] },
    };
    var render = function () {
      Object.keys(STYLE).forEach(function (k) {
        card.querySelectorAll("[data-hww-" + k + "]").forEach(function (b) {
          var on = Number(b.getAttribute("data-hww-" + k)) === sel[k];
          b.setAttribute("aria-pressed", String(on));
          swap(b, on ? STYLE[k].off : STYLE[k].on, on ? STYLE[k].on : STYLE[k].off);
          if (k === "season") {
            var t = b.querySelector("span");
            swap(t, on ? ["text-[#fff]/85"] : ["text-[#d9f99d]"], on ? ["text-[#d9f99d]"] : ["text-[#fff]/85"]);
          }
        });
      });
      label.textContent = "Book " + SEASONS[sel.season] + " plan · " + DAYS[sel.day] + " " + SLOTS[sel.slot];
    };
    card.addEventListener("click", function (e) {
      var b = e.target.closest("[data-hww-season],[data-hww-day],[data-hww-slot]");
      if (!b) return;
      Object.keys(STYLE).forEach(function (k) {
        if (b.hasAttribute("data-hww-" + k)) sel[k] = Number(b.getAttribute("data-hww-" + k));
      });
      render();
    });
  }

  /** Controller for one card: timers run only while active AND on screen. */
  function makeCard(card) {
    var kind = card.getAttribute("data-hww-card");
    var reduce = Arka.reduceMotion;
    var ticker = tickerFor(card, kind);
    var c = { el: card, active: false, inView: false, idx: 0, timer: 0 };
    if (kind === "book") initBook(card);
    if (!reduce) card.classList.add("ak-hww-arm");

    var sync = function () {
      var run = ticker && !reduce && c.active && c.inView;
      if (run && !c.timer) {
        if (ticker.start) ticker.start();
        c.timer = window.setInterval(function () {
          c.idx = (c.idx + 1) % ticker.count;
          ticker.render(c.idx);
        }, ticker.period);
      } else if (!run && c.timer) {
        window.clearInterval(c.timer);
        c.timer = 0;
      }
    };
    /** Replay the card's mount: entrance animations + ticker back to the first state. */
    c.play = function () {
      if (ticker) {
        if (c.timer) { window.clearInterval(c.timer); c.timer = 0; }
        c.idx = 0;
        ticker.render(0);
      }
      if (!reduce) {
        card.classList.remove("is-play");
        void card.offsetWidth; // restart the CSS transitions
        card.classList.add("is-play");
      }
      sync();
    };
    c.setActive = function (on) { c.active = on; sync(); };
    c.setInView = function (on) { c.inView = on; sync(); };
    return c;
  }

  /* ------------------------------------------------------------------ */
  /* sections                                                             */
  /* ------------------------------------------------------------------ */

  var DOT = {
    on: ["scale-110", "border-[#8CBF5F]", "bg-[#8CBF5F]", "text-[#06201e]", "shadow-[0_0_0_8px_rgba(140,191,95,0.22)]"],
    done: ["border-[#8CBF5F]", "bg-[#06201e]", "text-[#8CBF5F]"],
    off: ["border-[#fff]/30", "bg-[#06201e]/80", "text-[#fff]/70", "group-hover:border-[#fff]/60"],
  };
  var ALL_DOT = [].concat(DOT.on, DOT.done, DOT.off);

  function initDesktop(section, io, cards) {
    var photos = section.querySelectorAll("[data-hww-photo]");
    var steps = section.querySelectorAll("[data-hww-step]");
    var texts = section.querySelectorAll("[data-hww-text]");
    var proofs = section.querySelectorAll("[data-hww-proof]");
    var bar = section.querySelector("[data-hww-bar]");
    var n = steps.length;
    var proofCards = Array.prototype.map.call(proofs, function (p) {
      var c = cards.get(p.querySelector("[data-hww-card]"));
      return c;
    });
    var active = 0;
    var outTimers = [];

    var swapIn = function (list, i, prev) {
      var el = list[i];
      var old = list[prev];
      if (old && old !== el) {
        old.classList.remove("is-on");
        old.classList.add("is-out");
        old.setAttribute("aria-hidden", "true");
        clearTimeout(outTimers[prev]);
        outTimers[prev] = setTimeout(function () { old.classList.remove("is-out"); }, 650);
      }
      el.classList.remove("is-out");
      el.classList.add("is-on");
      el.removeAttribute("aria-hidden");
    };

    var setActive = function (i) {
      if (i === active) return;
      var prev = active;
      active = i;
      photos.forEach(function (ph, k) {
        var on = k === i;
        ph.classList.toggle("is-on", on);
        ph.setAttribute("aria-hidden", String(!on));
        var img = ph.querySelector("img");
        img.alt = on ? img.getAttribute("data-alt") : "";
      });
      steps.forEach(function (b, k) {
        var on = k === i;
        var done = k < i;
        var dot = b.querySelector("[data-hww-dot]");
        swap(dot, ALL_DOT, on ? DOT.on : done ? DOT.done : DOT.off);
        dot.querySelector("[data-hww-check]").hidden = !done;
        dot.querySelector("[data-hww-icon]").hidden = done;
        var label = b.querySelector("[data-hww-label]");
        swap(label, on ? ["text-[#fff]/60"] : ["text-[#fff]"], on ? ["text-[#fff]"] : ["text-[#fff]/60"]);
        if (on) b.setAttribute("aria-current", "step"); else b.removeAttribute("aria-current");
      });
      swapIn(texts, i, prev);
      swapIn(proofs, i, prev);
      proofs[prev].inert = true;
      proofs[i].inert = false;
      proofCards[prev].setActive(false);
      // the new card mounts after the old one has left (AnimatePresence mode="wait")
      proofCards[i].setActive(true);
      proofCards[i].play();
    };

    var progressToIndex = function (p) { return Math.min(n - 1, Math.max(0, Math.floor(p * n))); };

    if (window.ScrollTrigger && window.gsap) {
      ScrollTrigger.create({
        trigger: section, start: "top top", end: "bottom bottom",
        onUpdate: function (self) { setActive(progressToIndex(self.progress)); },
        onRefresh: function (self) { setActive(progressToIndex(self.progress)); },
      });
      gsap.fromTo(bar, { scaleX: 0.02 }, {
        scaleX: 1, ease: "none",
        scrollTrigger: { trigger: section, start: "top top", end: "bottom bottom", scrub: Arka.reduceMotion ? true : 0.6 },
      });
    } else {
      var onScroll = function () {
        var r = section.getBoundingClientRect();
        var span = section.offsetHeight - window.innerHeight;
        var p = span > 0 ? Math.min(1, Math.max(0, -r.top / span)) : 0;
        bar.style.transform = "scaleX(" + (0.02 + 0.98 * p) + ")";
        setActive(progressToIndex(p));
      };
      window.addEventListener("scroll", onScroll, { passive: true });
      onScroll();
    }

    section.addEventListener("click", function (e) {
      var b = e.target.closest("[data-hww-step]");
      if (!b) return;
      var i = Number(b.getAttribute("data-hww-step"));
      var top = section.getBoundingClientRect().top + window.scrollY;
      Arka.scrollTo(top + (section.offsetHeight - window.innerHeight) * ((i + 0.5) / n), 1.2);
    });

    // first chapter's card is mounted from the start
    proofs.forEach(function (p, k) { p.inert = k !== active; });
    proofCards[active].setActive(true);
    proofCards[active].play();
  }

  Arka.onReady(function () {
    var cards = new Map();
    var io = "IntersectionObserver" in window ? new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        var c = cards.get(en.target);
        if (!c) return;
        c.setInView(en.isIntersecting);
        // mobile cards mount (play their entrance) the first time they scroll into view
        if (en.isIntersecting && c.mobile && !c.played) { c.played = true; c.play(); }
      });
    }, { threshold: 0.15 }) : null;

    document.querySelectorAll("[data-hww-card]").forEach(function (el) {
      var c = makeCard(el);
      c.mobile = !!el.closest("#how-we-work-mobile");
      if (c.mobile) c.active = true;
      cards.set(el, c);
      if (io) io.observe(el); else { c.setInView(true); if (c.mobile) c.play(); }
    });

    var section = document.getElementById("how-we-work");
    if (section) initDesktop(section, io, cards);
  });
})();
