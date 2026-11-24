/*
 * ArkaShine website (Django) — shared behaviour for every website page.
 * Replaces the design's React pieces: SmoothScroll, SiteNav, LoginMenu, DemoModal,
 * and Motion's whileInView reveals.
 *
 * Markup hooks:
 *   data-scroll-to="<id>|top"   smooth-scroll to a section
 *   data-open="<name>"          open the dialog  [data-modal="<name>"]
 *   data-close                  close the dialog it sits in (or the open one)
 *   data-login-menu / data-login-toggle    header login dropdown
 *   .rv                         fades/slides in when scrolled into view
 *
 * Section scripts use the small API on window.Arka (see bottom).
 */
(function () {
  "use strict";

  var doc = document.documentElement;
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var lenis = null;

  /* ---------------- smooth scroll (Lenis + GSAP ScrollTrigger) ---------------- */
  function initSmoothScroll() {
    if (window.gsap && window.ScrollTrigger) window.gsap.registerPlugin(window.ScrollTrigger);
    if (reduceMotion || !window.Lenis) return;
    lenis = new window.Lenis({
      duration: 1.15,
      easing: function (t) { return Math.min(1, 1.001 - Math.pow(2, -10 * t)); },
      smoothWheel: true,
      touchMultiplier: 1.6,
    });
    if (window.gsap) {
      if (window.ScrollTrigger) lenis.on("scroll", window.ScrollTrigger.update);
      window.gsap.ticker.add(function (time) { lenis.raf(time * 1000); });
      window.gsap.ticker.lagSmoothing(0);
    } else {
      var raf = function (t) { lenis.raf(t); requestAnimationFrame(raf); };
      requestAnimationFrame(raf);
    }
  }

  /** Smooth scroll to an element id ("top" = page top) or an absolute y. */
  function scrollToTarget(target, duration) {
    var y = 0;
    if (typeof target === "number") y = target;
    else if (target && target !== "top") {
      var el = document.getElementById(target);
      if (!el) return;
      y = el.getBoundingClientRect().top + window.scrollY;
    }
    if (lenis) lenis.scrollTo(y, { duration: duration || 1.8 });
    else window.scrollTo({ top: y, behavior: reduceMotion ? "auto" : "smooth" });
  }

  /* ---------------- header: transparent over the hero, solid after ---------------- */
  var SCROLLED = ["home-light", "border-ivory/10", "bg-forest-deep/90", "shadow-sm", "backdrop-blur-xl"];
  var TOP = ["home-keep", "border-transparent"];
  function initHeader() {
    var header = document.querySelector("[data-site-header]");
    if (!header) return;
    var state = null;
    var update = function () {
      var hero = document.getElementById("top");
      var limit = hero ? hero.offsetHeight - window.innerHeight * 0.6 : 40;
      var scrolled = window.scrollY > limit;
      if (scrolled === state) return;
      state = scrolled;
      SCROLLED.forEach(function (c) { header.classList.toggle(c, scrolled); });
      TOP.forEach(function (c) { header.classList.toggle(c, !scrolled); });
    };
    update();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
  }

  /* ---------------- login dropdown ---------------- */
  function initLoginMenu() {
    document.querySelectorAll("[data-login-menu]").forEach(function (wrap) {
      var btn = wrap.querySelector("[data-login-toggle]");
      var menu = wrap.querySelector("[role=menu]");
      if (!btn || !menu) return;
      var chevron = btn.querySelectorAll("svg")[1];
      var setOpen = function (open) {
        btn.setAttribute("aria-expanded", String(open));
        if (chevron) chevron.classList.toggle("rotate-180", open);
        if (open) {
          menu.hidden = false;
          requestAnimationFrame(function () { menu.classList.add("is-open"); });
        } else {
          menu.classList.remove("is-open");
          setTimeout(function () { if (!menu.classList.contains("is-open")) menu.hidden = true; }, 200);
        }
      };
      btn.addEventListener("click", function () { setOpen(btn.getAttribute("aria-expanded") !== "true"); });
      document.addEventListener("mousedown", function (e) { if (!wrap.contains(e.target)) setOpen(false); });
      document.addEventListener("keydown", function (e) { if (e.key === "Escape") setOpen(false); });
    });
  }

  /* ---------------- dialogs ---------------- */
  var openStack = [];
  function openModal(name) {
    var m = document.querySelector('[data-modal="' + name + '"]');
    if (!m) return null;
    m.hidden = false;
    m.dispatchEvent(new CustomEvent("ak:open", { bubbles: true }));
    requestAnimationFrame(function () { m.classList.add("is-open"); });
    openStack.push(m);
    doc.classList.add("ak-locked");
    if (lenis) lenis.stop();
    // move focus into the dialog (the panel itself, so no control shows a stray focus ring)
    var panel = m.querySelector(".ak-dialog") || m;
    if (!panel.hasAttribute("tabindex")) panel.setAttribute("tabindex", "-1");
    setTimeout(function () { panel.focus({ preventScroll: true }); }, 60);
    return m;
  }
  function closeModal(m) {
    m = m || openStack[openStack.length - 1];
    if (!m) return;
    m.classList.remove("is-open");
    openStack = openStack.filter(function (x) { return x !== m; });
    setTimeout(function () { if (!m.classList.contains("is-open")) m.hidden = true; m.dispatchEvent(new CustomEvent("ak:close", { bubbles: true })); }, 320);
    if (!openStack.length) {
      doc.classList.remove("ak-locked");
      if (lenis) lenis.start();
    }
  }
  function initModals() {
    document.addEventListener("click", function (e) {
      var closer = e.target.closest("[data-close]");
      var opener = e.target.closest("[data-open]");
      var scroller = e.target.closest("[data-scroll-to]");
      if (closer) closeModal(closer.closest("[data-modal]"));
      if (opener) { e.preventDefault(); openModal(opener.getAttribute("data-open")); }
      if (scroller) {
        e.preventDefault();
        var id = scroller.getAttribute("data-scroll-to");
        // let a closing menu release the scroll lock first
        setTimeout(function () { scrollToTarget(id, 1.8); }, closer ? 340 : 0);
      }
    });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && openStack.length) closeModal(); });
  }

  /* ---------------- reveal on scroll (Motion whileInView) ---------------- */
  function initReveal(root) {
    var els = (root || document).querySelectorAll(".rv:not(.is-in)");
    if (!("IntersectionObserver" in window) || reduceMotion) {
      els.forEach(function (el) { el.classList.add("is-in"); });
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        // small stagger between reveal siblings, like Motion's stagger groups
        var sibs = Array.prototype.filter.call(en.target.parentElement ? en.target.parentElement.children : [], function (c) { return c.classList.contains("rv"); });
        var i = Math.max(0, sibs.indexOf(en.target));
        en.target.style.setProperty("--rv-delay", Math.min(i * 0.08, 0.48) + "s");
        en.target.classList.add("is-in");
        io.unobserve(en.target);
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.12 });
    els.forEach(function (el) { io.observe(el); });
  }

  /* ---------------- "Book a demo" form → Django /website-enquiry/ ---------------- */
  function csrfToken(form) {
    var i = form && form.querySelector("input[name=csrfmiddlewaretoken]");
    if (i) return i.value;
    var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  /** POST a JSON enquiry to Django. Resolves {ok, error}. */
  function sendEnquiry(form, data) {
    return fetch(form.getAttribute("action"), {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", Accept: "application/json", "X-CSRFToken": csrfToken(form) },
      body: JSON.stringify(data),
    }).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (body) {
        return res.ok && body.ok ? { ok: true } : { ok: false, error: body.error || "Could not send right now" };
      });
    }).catch(function () { return { ok: false, error: "Could not send right now" }; });
  }

  var ORG_ON = ["bg-white", "text-[#0C0F14]", "font-medium", "border-white"];
  var ORG_OFF = ["bg-white/5", "border-white/10", "text-white/70", "hover:border-white/20"];
  var DOT = { on: ["w-8", "bg-[#2F6F62]"], done: ["w-4", "bg-white/40"], off: ["w-4", "bg-white/10"] };

  function initDemo() {
    var form = document.querySelector("[data-demo-form]");
    if (!form) return;
    var modal = form.closest("[data-modal]");
    var step = 1;
    var $ = function (s) { return form.querySelector(s); };
    var err = $("[data-demo-error]");
    var showError = function (msg) { err.textContent = msg || ""; err.hidden = !msg; };

    var render = function () {
      form.querySelectorAll("[data-step]").forEach(function (s) { s.hidden = Number(s.getAttribute("data-step")) !== step; });
      form.querySelectorAll("[data-step-dot]").forEach(function (d) {
        var i = Number(d.getAttribute("data-step-dot"));
        var want = i === step ? DOT.on : i < step ? DOT.done : DOT.off;
        [].concat(DOT.on, DOT.done, DOT.off).forEach(function (c) { d.classList.remove(c); });
        want.forEach(function (c) { d.classList.add(c); });
      });
      $("[data-step-no]").textContent = String(step);
      $("[data-demo-back]").hidden = step === 1;
      $("[data-demo-spacer]").hidden = step !== 1;
      $("[data-demo-next-label]").textContent = step === 3 ? "Confirm Demo" : "Proceed";
    };
    var reset = function () {
      step = 1;
      form.reset();
      $("[data-demo-done]").hidden = true;
      $("[data-demo-steps]").hidden = false;
      selectOrg(form.querySelector("[data-org]"));
      showError("");
      render();
    };
    var selectOrg = function (btn) {
      if (!btn) return;
      form.querySelectorAll("[data-org]").forEach(function (b) {
        var on = b === btn;
        b.setAttribute("aria-checked", String(on));
        (on ? ORG_OFF : ORG_ON).forEach(function (c) { b.classList.remove(c); });
        (on ? ORG_ON : ORG_OFF).forEach(function (c) { b.classList.add(c); });
      });
      form.elements.orgType.value = btn.getAttribute("data-org");
    };

    form.addEventListener("input", function () { if (!err.hidden) showError(""); });
    form.addEventListener("click", function (e) {
      var org = e.target.closest("[data-org]");
      if (org) selectOrg(org);
      if (e.target.closest("[data-demo-back]") && step > 1) { step -= 1; showError(""); render(); }
    });
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (step < 3) { step += 1; render(); return; }
      var v = function (n) { return (form.elements[n].value || "").trim(); };
      if (!v("name") || !v("phone") || !v("email") || !v("date")) {
        showError("Please add your name, phone, email and a preferred date.");
        return;
      }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v("email"))) { showError("Please enter a valid email."); return; }
      showError("");
      var next = $("[data-demo-next]");
      next.disabled = true;
      $("[data-demo-next-label]").textContent = "Sending…";
      sendEnquiry(form, {
        type: "Demo booking", audience: "general", page: window.location.pathname,
        name: v("name"), phone: v("phone"), email: v("email"), date: v("date"),
        orgType: v("orgType"), location: v("location"),
      }).then(function (r) {
        next.disabled = false;
        if (!r.ok) {
          render();
          showError("We couldn't send your booking right now. Please try again, or WhatsApp us on +91 96112 97893.");
          return;
        }
        $("[data-demo-name]").textContent = v("name") || "you";
        $("[data-demo-steps]").hidden = true;
        $("[data-demo-done]").hidden = false;
      });
    });
    if (modal) modal.addEventListener("ak:close", function () { if (!$("[data-demo-done]").hidden) reset(); });
    render();
  }

  /* ---------------- boot ---------------- */
  var readyFns = [];
  var booted = false;
  /** Section scripts register their init here; it runs after the shared setup. */
  function onReady(fn) {
    if (booted) { try { fn(); } catch (e) { console.error(e); } initReveal(); }
    else readyFns.push(fn);
  }

  window.Arka = {
    get lenis() { return lenis; },
    reduceMotion: reduceMotion,
    scrollTo: scrollToTarget,
    openModal: openModal,
    closeModal: closeModal,
    reveal: initReveal,
    sendEnquiry: sendEnquiry,
    onReady: onReady,
  };

  function boot() {
    if (booted) return;
    booted = true;
    initSmoothScroll();
    initHeader();
    initLoginMenu();
    initModals();
    initDemo();
    readyFns.forEach(function (fn) { try { fn(); } catch (e) { console.error(e); } });
    initReveal();
    if (window.ScrollTrigger) window.ScrollTrigger.refresh();
  }
  // deferred scripts run before DOMContentLoaded: wait so every section script has registered
  if (document.readyState === "complete") boot();
  else document.addEventListener("DOMContentLoaded", boot);
})();
