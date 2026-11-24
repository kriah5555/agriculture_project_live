/* homepage section script — see templates/website/partials/home/_patents.html
 * Design: PatentShowcase. Granted-patent cards (rotateX entrance) → details drawer;
 * "10 more patents" → modal with a 3D ring that auto-advances every 2600ms. */
(function () {
  "use strict";

  function initCards(section) {
    var cards = section.querySelectorAll(".ak-pcard");
    var show = function (card) {
      card.classList.add("is-in");
      // once the entrance is over, drop the stagger so hover reacts at once
      setTimeout(function () { card.classList.add("is-done"); }, 1200);
    };
    cards.forEach(function (c, i) { c.style.setProperty("--pc-delay", i * 0.1 + "s"); });
    if (Arka.reduceMotion || !("IntersectionObserver" in window)) { cards.forEach(show); return; }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        show(en.target);
        io.unobserve(en.target);
      });
    }, { threshold: 0.3 });
    cards.forEach(function (c) { io.observe(c); });
  }

  function initDrawer(section) {
    var modal = section.querySelector('[data-modal="patent"]');
    if (!modal) return;
    section.querySelectorAll("[data-patent]").forEach(function (card) {
      card.addEventListener("click", function () {
        var d = card.dataset;
        modal.querySelectorAll("[data-field]").forEach(function (el) {
          el.textContent = d[el.getAttribute("data-field")] || "";
        });
        modal.setAttribute("aria-label", d.number + " " + d.title);
        modal.querySelector(".ak-drawer").scrollTop = 0;
        Arka.openModal("patent");
      });
    });
  }

  var ON = ["border-transparent", "bg-[#1E7A33]", "text-[#fff]"];
  var OFF = ["border-[#162a54]/10", "bg-[#fff]", "text-[#162a54]"];
  var PARTS = {
    "[data-ring-icon]": ["text-[#fff]", "text-[#1E7A33]"],
    "[data-ring-no]": ["text-[#fff]/40", "text-[#162a54]/15"],
    "[data-ring-app]": ["text-[#fff]/80", "text-[#5b6575]"],
    "[data-ring-status]": ["text-[#fff]/85", "text-[#5b6575]"],
  };
  function swap(el, on, pair) {
    el.classList.remove.apply(el.classList, on ? pair[1] : pair[0]);
    el.classList.add.apply(el.classList, on ? pair[0] : pair[1]);
  }

  function initRing(section) {
    var modal = section.querySelector('[data-modal="patents-more"]');
    if (!modal) return;
    var ring = modal.querySelector("[data-ring]");
    var cards = modal.querySelectorAll("[data-ring-card]");
    var caps = modal.querySelectorAll("[data-ring-caption]");
    var n = cards.length;
    var stepDeg = 360 / n;
    var front = 0;
    var turn = 0; // cumulative ring position, so 10 → 1 keeps turning forward
    var playing = false;
    var timer = null;

    var render = function () {
      ring.style.transform = "rotateY(" + -turn * stepDeg + "deg)";
      cards.forEach(function (c, i) {
        var on = i === front;
        var face = c.querySelector("[data-ring-face]");
        swap(face, on, [ON, OFF]);
        Object.keys(PARTS).forEach(function (sel) {
          var el = face.querySelector(sel);
          if (el) swap(el, on, [[PARTS[sel][0]], [PARTS[sel][1]]]);
        });
        c.setAttribute("aria-current", on ? "true" : "false");
      });
      caps.forEach(function (p, i) {
        var on = i === front;
        if (on) {
          p.classList.remove("is-out");
          if (p.hidden) {
            p.hidden = false;
            requestAnimationFrame(function () { requestAnimationFrame(function () { if (Number(p.getAttribute("data-ring-caption")) === front) p.classList.add("is-on"); }); });
          }
        } else if (!p.hidden) {
          p.classList.remove("is-on");
          p.hidden = true;
        }
      });
    };
    var go = function (i) {
      var target = ((i % n) + n) % n;
      var diff = target - front;
      if (diff > n / 2) diff -= n;
      if (diff < -n / 2) diff += n;
      turn += diff;
      front = target;
      render();
    };
    var setPlaying = function (v) {
      playing = v;
      clearInterval(timer);
      timer = v ? setInterval(function () { go(front + 1); }, 2600) : null;
      modal.querySelector("[data-ring-pause]").hidden = !v;
      modal.querySelector("[data-ring-play]").hidden = v;
      modal.querySelector("[data-ring-label]").textContent = v ? "Pause" : "Rotate";
    };

    cards.forEach(function (c, i) { c.addEventListener("click", function () { go(i); setPlaying(false); }); });
    modal.querySelector("[data-ring-prev]").addEventListener("click", function () { go(front - 1); setPlaying(false); });
    modal.querySelector("[data-ring-next]").addEventListener("click", function () { go(front + 1); setPlaying(false); });
    modal.querySelector("[data-ring-toggle]").addEventListener("click", function () { setPlaying(!playing); });

    // the React modal remounts on each open: start at patent 01, playing unless reduced motion
    modal.addEventListener("ak:open", function () {
      ring.style.transition = "none";
      front = 0;
      turn = 0;
      render();
      ring.offsetWidth; // apply the reset without animating it
      ring.style.transition = "";
      setPlaying(!Arka.reduceMotion);
    });
    modal.addEventListener("ak:close", function () { setPlaying(false); });
  }

  Arka.onReady(function () {
    var section = document.getElementById("patents");
    if (!section) return;
    initCards(section);
    initDrawer(section);
    initRing(section);
  });
})();
