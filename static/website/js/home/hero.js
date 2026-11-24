/*
 * Homepage hero — "Soil is more than what you see" scroll film.
 * Port of the design's SoilToFarmHero (React) to plain JS:
 *   - WebGL soil film: window.ArkaSoilFilm (static/website/js/arka-film.js)
 *   - scroll choreography: GSAP ScrollTrigger, scrubbed by page scroll
 * Markup: templates/website/partials/home/_hero.html (data-hero="…")
 */
(function () {
  "use strict";

  var CHAPTERS = [
    { at: 0, label: "Living soil & mud" },
    { at: 0.08, label: "Underground soil" },
    { at: 0.17, label: "Root network" },
    { at: 0.27, label: "Nutrient particles" },
    { at: 0.38, label: "Golden sunlight" },
    { at: 0.55, label: "Green farm" },
  ];
  var FALLBACK_PLATES = [
    "images/hero-living-soil.webp",
    "images/generated/hero_scene_3_healthy_soil_roots.jpg",
    "images/generated/hero_scene_2_microscopic_nutrients.jpg",
    "images/farm-sunrise.webp",
  ];

  function hasWebGL() {
    try {
      var c = document.createElement("canvas");
      return !!(c.getContext("webgl2") || c.getContext("webgl"));
    } catch (e) {
      return false;
    }
  }

  function init() {
    var section = document.querySelector("[data-hero-section]");
    if (!section || !window.gsap || !window.ScrollTrigger) return;
    var gsap = window.gsap;
    var ScrollTrigger = window.ScrollTrigger;
    var $ = function (k) { return section.querySelector('[data-hero="' + k + '"]'); };
    var canvas = $("canvas"), poster = $("poster");
    var film = null;
    var fallback = null;
    var progress = 0;

    /* ---------- WebGL film (falls back to still plates) ---------- */
    var off = new URLSearchParams(window.location.search).get("3d") === "0";
    if (off || !hasWebGL() || !window.ArkaSoilFilm) {
      fallback = document.createElement("div");
      fallback.setAttribute("aria-hidden", "true");
      fallback.className = "absolute inset-0";
      FALLBACK_PLATES.forEach(function (src, i) {
        var d = document.createElement("div");
        d.setAttribute("data-plate", "");
        d.className = "absolute inset-0 bg-cover bg-center";
        d.style.backgroundImage = "url(" + window.ARKA_ASSET + src + ")";
        d.style.opacity = i === 0 ? "1" : "0";
        if (i < 3) d.style.filter = "brightness(0.75)";
        fallback.appendChild(d);
      });
      canvas.insertAdjacentElement("afterend", fallback);
    } else {
      var quality = window.innerWidth < 768 || (navigator.hardwareConcurrency || 8) <= 4 ? "low" : "high";
      try {
        film = window.ArkaSoilFilm.createSoilFilm(canvas, quality);
        var size = function () { film.resize(canvas.clientWidth || window.innerWidth, canvas.clientHeight || window.innerHeight); };
        size();
        new ResizeObserver(size).observe(canvas);
        new IntersectionObserver(function (en) { film.setActive(en[0].isIntersecting); }, { rootMargin: "100px" }).observe(section);
        window.addEventListener("pointermove", function (e) {
          film.setPointer((e.clientX / window.innerWidth) * 2 - 1, -((e.clientY / window.innerHeight) * 2 - 1));
        }, { passive: true });
        film.setProgress(progress);
        film.ready.then(function () {
          canvas.classList.replace("opacity-0", "opacity-100");
          poster.classList.replace("opacity-100", "opacity-0");
        });
      } catch (e) {
        console.warn("[hero] soil film unavailable", e);
        film = null;
      }
    }

    /* ---------- intro: blur-to-sharp entrance of the headline ---------- */
    gsap.fromTo(section.querySelectorAll("[data-intro]"),
      { opacity: 0, y: 28, filter: "blur(14px)" },
      { opacity: 1, y: 0, filter: "blur(0px)", duration: 1.4, ease: "power3.out", stagger: 0.14, delay: 0.35 });

    /* ---------- scroll timeline (progress 0 → 1 over the pinned section) ---------- */
    var q = function (s) { return section.querySelectorAll(s); };
    var tl = gsap.timeline({ paused: true, defaults: { ease: "none" } });
    tl.fromTo(q("[data-mud-img]"),
        { scale: 1.0, filter: "brightness(0.92) contrast(1.04) blur(0px)" },
        { scale: 1.35, filter: "brightness(1.05) contrast(1.08) blur(12px)", duration: 0.12, ease: "power1.inOut" }, 0.0)
      .to($("mud"), { opacity: 0, duration: 0.05, ease: "power2.out" }, 0.08);
    tl.to($("textA"), { opacity: 0, y: -48, filter: "blur(16px)", duration: 0.07 }, 0.07)
      .to($("cue"), { opacity: 0, duration: 0.03 }, 0.02)
      .fromTo($("textB"), { opacity: 0, y: 48, filter: "blur(18px)" }, { opacity: 1, y: 0, filter: "blur(0px)", duration: 0.07, ease: "power2.out" }, 0.73)
      .fromTo(q("[data-farm-line]"), { opacity: 0, y: 20 }, { opacity: 1, y: 0, stagger: 0.012, duration: 0.04 }, 0.76)
      .to($("textB"), { opacity: 0, y: -36, filter: "blur(12px)", duration: 0.05 }, 0.90)
      .fromTo($("dissolve"), { opacity: 0 }, { opacity: 1, duration: 0.025 }, 0.975)
      .to($("rail"), { opacity: 0, duration: 0.04 }, 0.68)
      .fromTo(q("[data-nutrient]"), { opacity: 0, scale: 0.2, y: 30 }, { opacity: 1, scale: 1, y: 0, duration: 0.02, ease: "back.out(2.6)", stagger: 0.006 }, 0.23)
      .fromTo(q("[data-nutrient-cap]"), { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 0.03 }, 0.27)
      .to(q("[data-nutrient]"), { opacity: 0, y: -60, scale: 0.85, duration: 0.04, stagger: 0.003 }, 0.43)
      .to(q("[data-nutrient-cap]"), { opacity: 0, duration: 0.03 }, 0.44)
      .fromTo($("photo"), { opacity: 0 }, { opacity: 1, duration: 0.04 }, 0.69)
      .fromTo(q("[data-photo-img]"), { scale: 1.06 }, { scale: 1, duration: 0.30 }, 0.69)
      .fromTo(q("[data-field-photo]"), { opacity: 0, y: 40, scale: 0.9 }, { opacity: 1, y: 0, scale: 1, duration: 0.03, ease: "back.out(1.8)", stagger: 0.012 }, 0.78)
      .set({}, {}, 1);
    if (fallback) {
      fallback.querySelectorAll("[data-plate]").forEach(function (el, i) {
        if (i === 0) return;
        tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: 0.08 }, [0, 0.25, 0.5, 0.75][i] || 0.75);
      });
    }

    /* ---------- chapter rail ---------- */
    var rail = $("rail"), live = $("chapterLive"), mob = $("chapterMobile");
    var labels = section.querySelectorAll("[data-chapter]");
    var last = -1;
    var setChapter = function (c) {
      labels.forEach(function (el, i) {
        el.classList.toggle("translate-x-1", i === c);
        el.classList.toggle("text-ivory", i === c);
        el.classList.toggle("text-ivory/70", i !== c);
      });
      if (live) live.textContent = CHAPTERS[c].label;
      if (mob) mob.textContent = String(c + 1).padStart(2, "0") + " · " + CHAPTERS[c].label;
    };

    ScrollTrigger.create({
      id: "soil-film",
      trigger: section,
      start: "top top",
      end: "bottom bottom",
      onUpdate: function (self) {
        progress = self.progress;
        if (film) film.setProgress(progress);
        tl.progress(progress);
        var c = 0;
        for (var i = 0; i < CHAPTERS.length; i++) if (progress >= CHAPTERS[i].at) c = i;
        if (c !== last) { last = c; setChapter(c); }
        if (rail) rail.style.setProperty("--p", String(Math.min(1, progress / 0.72)));
      },
    });

    /* "Explore our technology": glide down to the farm chapter */
    var descend = $("descend");
    if (descend) descend.addEventListener("click", function () {
      var top = section.getBoundingClientRect().top + window.scrollY;
      window.Arka.scrollTo(top + (section.offsetHeight - window.innerHeight) * 0.72, 7);
    });
  }

  window.Arka.onReady(init);
})();
