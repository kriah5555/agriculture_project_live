/* Shared PDF download progress (navbar pages + standalone report). */
  /* PDF downloads: show progress while the server builds the PDF (they can take a while),
     prevent double clicks, save with the server's filename, and report errors.
     Applies to same-origin links whose path contains "pdf"; opt out with data-no-pdf-progress. */
  (function () {
    var css = "@keyframes pdfSpin{to{transform:rotate(360deg)}}@keyframes pdfIn{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}" +
      ".pdf-toast{position:fixed;right:20px;bottom:20px;z-index:10060;width:320px;max-width:calc(100vw - 32px);background:var(--tc-surface,#fff);color:var(--tc-text,#1a1a1a);" +
      "border-radius:14px;box-shadow:0 12px 34px rgba(0,0,0,.22);border:1px solid var(--tc-border,#dee2e6);overflow:hidden;animation:pdfIn .3s both;font-size:13px}" +
      ".pdf-toast-h{display:flex;align-items:center;gap:10px;padding:12px 14px}" +
      ".pdf-toast-ic{width:34px;height:34px;border-radius:10px;flex-shrink:0;display:flex;align-items:center;justify-content:center;color:#fff;background:linear-gradient(135deg,#15803d,#0d9488)}" +
      ".pdf-toast.err .pdf-toast-ic{background:#dc2626}.pdf-toast.ok .pdf-toast-ic{background:#16a34a}" +
      ".pdf-toast-t{font-weight:700}.pdf-toast-s{font-size:12px;color:var(--tc-text-muted,#6c757d)}" +
      ".pdf-toast-x{margin-left:auto;border:none;background:transparent;color:var(--tc-text-muted,#6c757d);font-size:12px;font-weight:600;cursor:pointer;padding:4px 6px;border-radius:6px}" +
      ".pdf-toast-x:hover{background:var(--tc-surface-alt,#f4f5f8)}" +
      ".pdf-bar{height:4px;background:var(--tc-surface-alt,#eef0f5);overflow:hidden}.pdf-bar i{display:block;height:100%;width:0;background:linear-gradient(90deg,#15803d,#0d9488);transition:width .6s ease}" +
      ".pdf-spin{width:16px;height:16px;border:2.5px solid rgba(255,255,255,.4);border-top-color:#fff;border-radius:50%;animation:pdfSpin .8s linear infinite}" +
      ".pdf-busy{pointer-events:none;opacity:.75}.pdf-busy .pdf-btn-spin{display:inline-block;width:12px;height:12px;border:2px solid currentColor;border-right-color:transparent;border-radius:50%;animation:pdfSpin .8s linear infinite;margin-right:6px;vertical-align:-1px}";
    var st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);

    function isPdfLink(a) {
      if (!a || a.hasAttribute("data-no-pdf-progress") || a.target === "_blank" || a.hasAttribute("download")) return false;
      var href = a.getAttribute("href") || "";
      if (!href || href.charAt(0) === "#" || href.indexOf("javascript:") === 0) return false;
      try { var u = new URL(a.href, location.href); } catch (e) { return false; }
      return u.origin === location.origin && /pdf/i.test(u.pathname);
    }

    function toast() {
      var el = document.createElement("div"); el.className = "pdf-toast"; el.setAttribute("role", "status");
      el.innerHTML = '<div class="pdf-toast-h"><div class="pdf-toast-ic"><span class="pdf-spin"></span></div>' +
        '<div style="min-width:0"><div class="pdf-toast-t">Generating your PDF\u2026</div><div class="pdf-toast-s">Preparing report \u00b7 0s</div></div>' +
        '<button type="button" class="pdf-toast-x">Cancel</button></div><div class="pdf-bar"><i></i></div>';
      document.body.appendChild(el); return el;
    }

    function filenameFrom(res, url) {
      var cd = res.headers.get("Content-Disposition") || "", m = cd.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
      if (m) { try { return decodeURIComponent(m[1]); } catch (e) { return m[1]; } }
      var last = new URL(url, location.href).pathname.split("/").filter(Boolean).pop() || "report";
      return /\.pdf$/i.test(last) ? last : last + ".pdf";
    }

    function start(a) {
      if (a.classList.contains("pdf-busy")) return;
      var url = a.href, t0 = Date.now(), ctrl = new AbortController(), done = false;
      a.classList.add("pdf-busy"); a.setAttribute("aria-busy", "true");
      var spin = document.createElement("span"); spin.className = "pdf-btn-spin"; a.insertBefore(spin, a.firstChild);
      var el = toast(), sub = el.querySelector(".pdf-toast-s"), bar = el.querySelector(".pdf-bar i"), x = el.querySelector(".pdf-toast-x");
      var stages = [[0, "Preparing report"], [4, "Analysing soil data"], [10, "Rendering pages"], [25, "Almost there"], [60, "Large report \u2014 still working"]];
      var tick = setInterval(function () {
        var s = Math.round((Date.now() - t0) / 1000), label = stages[0][1];
        stages.forEach(function (g) { if (s >= g[0]) label = g[1]; });
        sub.textContent = label + " \u00b7 " + s + "s";
        bar.style.width = Math.min(92, 100 * (1 - Math.exp(-s / 18))) + "%";   // eases toward 92% until done
      }, 500);
      function finish() { clearInterval(tick); a.classList.remove("pdf-busy"); a.removeAttribute("aria-busy"); spin.remove(); done = true; }
      function close(ms) { setTimeout(function () { el.remove(); }, ms); }
      x.onclick = function () { if (!done) { ctrl.abort(); } else { el.remove(); } };

      fetch(url, { credentials: "same-origin", signal: ctrl.signal }).then(function (res) {
        var type = (res.headers.get("Content-Type") || "").toLowerCase();
        if (res.ok && type.indexOf("pdf") === -1 && type.indexOf("octet-stream") === -1) {
          // Not a file (e.g. login page or an HTML error view): let the browser handle the link normally.
          finish(); el.remove(); location.href = url; return null;
        }
        if (!res.ok) throw new Error("Server returned " + res.status);
        return res.blob().then(function (blob) { return { blob: blob, name: filenameFrom(res, url) }; });
      }).then(function (r) {
        if (!r) return;
        var obj = URL.createObjectURL(r.blob), dl = document.createElement("a");
        dl.href = obj; dl.download = r.name; document.body.appendChild(dl); dl.click(); dl.remove();
        setTimeout(function () { URL.revokeObjectURL(obj); }, 60000);
        finish(); bar.style.width = "100%"; el.classList.add("ok");
        el.querySelector(".pdf-toast-ic").innerHTML = '<i class="fas fa-check"></i>';
        el.querySelector(".pdf-toast-t").textContent = "Downloaded";
        sub.textContent = r.name + " \u00b7 " + Math.round((Date.now() - t0) / 1000) + "s";
        x.textContent = "Close"; close(5000);
      }).catch(function (err) {
        finish();
        if (err && err.name === "AbortError") { el.remove(); return; }
        el.classList.add("err");
        el.querySelector(".pdf-toast-ic").innerHTML = '<i class="fas fa-exclamation"></i>';
        el.querySelector(".pdf-toast-t").textContent = "Couldn't create the PDF";
        sub.textContent = (err && err.message) || "Network error";
        x.textContent = "Retry"; x.onclick = function () { el.remove(); start(a); };
        close(15000);
      });
    }

    document.addEventListener("click", function (e) {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      var a = e.target.closest && e.target.closest("a[href]");
      if (!isPdfLink(a)) return;
      e.preventDefault(); start(a);
    });
  })();

