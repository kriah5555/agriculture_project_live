/* homepage section script — see templates/website/partials/home/_faq.html and _contact_footer.html
 * Design: FaqContact. FAQ accordion, closing-headline blur-in, newsletter thank-you.
 * Book a Demo / Request a Quote / Terms use the global data-open dialogs (site.js). */
(function () {
  "use strict";

  function initFaq() {
    var list = document.querySelector("[data-faq]");
    if (!list) return;
    var qs = list.querySelectorAll("[data-faq-q]");
    var setOpen = function (btn, on) {
      var panel = document.getElementById(btn.getAttribute("aria-controls"));
      btn.setAttribute("aria-expanded", String(on));
      var label = btn.querySelector("span");
      label.classList.toggle("text-ivory", on);
      label.classList.toggle("text-ivory/75", !on);
      btn.querySelector("svg").classList.toggle("rotate-45", on);
      if (panel) {
        panel.classList.toggle("is-open", on);
        panel.setAttribute("aria-hidden", String(!on));
      }
    };
    qs.forEach(function (btn) {
      setOpen(btn, btn.getAttribute("aria-expanded") === "true");
      btn.addEventListener("click", function () {
        var wasOpen = btn.getAttribute("aria-expanded") === "true";
        qs.forEach(function (b) { setOpen(b, false); });
        if (!wasOpen) setOpen(btn, true);
      });
    });
  }

  function initHeadline() {
    var h = document.querySelector("#contact .ak-blurin");
    if (!h) return;
    if (Arka.reduceMotion || !("IntersectionObserver" in window)) { h.classList.add("is-in"); return; }
    var io = new IntersectionObserver(function (entries) {
      if (!entries[0].isIntersecting) return;
      h.classList.add("is-in");
      io.disconnect();
    }, { threshold: 0.5 });
    io.observe(h);
  }

  function initNewsletter() {
    var form = document.querySelector("[data-newsletter]");
    if (!form) return;
    var done = form.parentElement.querySelector("[data-newsletter-done]");
    // the browser validates the email (type=email, required); no backend, as in the design
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      form.reset();
      if (done) done.hidden = false;
    });
    form.addEventListener("input", function () { if (done) done.hidden = true; });
  }

  Arka.onReady(function () {
    initFaq();
    initHeadline();
    initNewsletter();
  });
})();
