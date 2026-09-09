/*
 * proof_library.js — the Moodlight proof library, embeddable.
 *
 * Squarespace embed:
 *   <div id="moodlight-proof"></div>
 *   <script src="https://moodlight-api-production.up.railway.app/static/proof_library.js?v=1"></script>
 *
 * Renders itself from /api/predictions/public, so the section updates as calls
 * resolve instead of being re-pasted by hand.
 *
 * OPEN CALLS LEAD, DELIBERATELY. A page of wins reads as cherry-picking, which
 * is the exact suspicion a track record exists to kill. A bet whose outcome
 * nobody knows yet is the only part that cannot be faked, so it goes first and
 * the resolved ones sit underneath as history - misses included.
 *
 * No evidence payloads are exposed here, matching the standalone page: rows
 * sealed before the 2026-09-08 capture fix carry evidence matched to a broad
 * topic rather than to the call.
 */
(function () {
  "use strict";

  var scriptTag = document.currentScript;
  var src = scriptTag ? scriptTag.src : "";
  var API = src
    ? src.replace(/\/static\/proof_library\.js.*$/, "")
    : "https://moodlight-api-production.up.railway.app";

  var VERDICT = {
    played_out: ["Played out", "#15803D", "#EAF6EE"],
    partial: ["Partial", "#B45309", "#FDF3E7"],
    missed: ["Missed", "#B91C1C", "#FBECEC"]
  };

  function el(tag, css, text) {
    var e = document.createElement(tag);
    if (css) e.style.cssText = css;
    if (text != null) e.textContent = text;
    return e;
  }

  function card(c) {
    var open = !c.status;
    var wrap = el("div", "padding:20px 0;border-bottom:1px solid #E7E9ED;");

    var head = el("div", "display:flex;gap:10px;align-items:center;flex-wrap:wrap;");
    var v = open ? ["Open", "#3C4453", "#EEF1F5"] : (VERDICT[c.status] || [c.status, "#3C4453", "#EEF1F5"]);
    head.appendChild(el("span",
      "display:inline-block;padding:3px 10px;border-radius:2px;background:" + v[2] +
      ";color:" + v[1] + ";font-size:11px;font-weight:700;letter-spacing:.08em;" +
      "text-transform:uppercase;", v[0]));
    head.appendChild(el("span",
      "color:#5A616E;font-size:12px;font-family:ui-monospace,Menlo,monospace;",
      "called " + c.called + (c.topic ? "  ·  " + c.topic : "")));
    wrap.appendChild(head);

    wrap.appendChild(el("div",
      "font-size:17px;line-height:1.5;margin-top:10px;color:#12151C;", c.statement));

    wrap.appendChild(el("div", "color:#5A616E;font-size:13px;margin-top:10px;",
      open ? "Resolves " + c.due : "Due " + c.due + "  ·  resolved " + c.resolved));

    // The specific evidence is the part that lands, so it is one click away
    // rather than buried on another page.
    if (!open && c.what_happened) {
      var d = document.createElement("details");
      d.style.cssText = "margin-top:12px;";
      var s = document.createElement("summary");
      s.style.cssText = "cursor:pointer;color:#C57A11;font-size:13px;font-weight:600;list-style:none;";
      s.textContent = "What happened ›";
      d.appendChild(s);
      d.appendChild(el("div",
        "margin-top:10px;padding:14px 16px;background:#FAFBFC;border-left:3px solid #C57A11;" +
        "font-size:14px;line-height:1.65;color:#2B2F38;white-space:pre-wrap;", c.what_happened));
      wrap.appendChild(d);
    }
    return wrap;
  }

  function render(host, data) {
    host.innerHTML = "";
    var root = el("div",
      "font-family:system-ui,-apple-system,'Segoe UI',Helvetica,sans-serif;" +
      "max-width:720px;margin:0 auto;color:#12151C;");

    root.appendChild(el("div",
      "font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#C57A11;font-weight:700;",
      "The proof library"));
    root.appendChild(el("h2",
      "font-size:30px;font-weight:600;margin:12px 0 10px;line-height:1.2;",
      "We write the call down before we know the answer."));
    root.appendChild(el("p",
      "font-size:16px;line-height:1.6;color:#3C4453;margin:0 0 6px;",
      "Every call is dated, the evidence is sealed the moment it is made, and it gets " +
      "checked against what actually happened. Including the ones we get wrong."));

    var tally = Object.keys(data.counts || {}).map(function (k) {
      return (VERDICT[k] ? VERDICT[k][0].toLowerCase() : k) + " " + data.counts[k];
    }).join("  ·  ") || "none resolved yet";
    root.appendChild(el("p",
      "font-size:14px;line-height:1.6;color:#5A616E;margin:0 0 36px;",
      data.total + " calls  ·  " + data.open + " still open  ·  " + tally));

    var openCalls = data.calls.filter(function (c) { return !c.status; });
    var done = data.calls.filter(function (c) { return c.status; });

    if (openCalls.length) {
      root.appendChild(el("h3",
        "font-size:13px;letter-spacing:.14em;text-transform:uppercase;color:#5A616E;" +
        "font-weight:700;margin:0 0 4px;", "Open — outcome not yet known"));
      openCalls.forEach(function (c) { root.appendChild(card(c)); });
    }
    if (done.length) {
      root.appendChild(el("h3",
        "font-size:13px;letter-spacing:.14em;text-transform:uppercase;color:#5A616E;" +
        "font-weight:700;margin:44px 0 4px;", "Resolved"));
      done.forEach(function (c) { root.appendChild(card(c)); });
    }

    root.appendChild(el("p",
      "font-size:13px;color:#6B7280;margin-top:36px;line-height:1.6;",
      "Resolution is a human judgement, never the engine grading itself."));
    host.appendChild(root);
  }

  function mount() {
    var host = document.getElementById("moodlight-proof");
    if (!host) return;
    fetch(API + "/api/predictions/public")
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d && d.calls && d.calls.length) render(host, d);
        else host.innerHTML = "";
      })
      .catch(function () {
        // Fail silently to nothing rather than showing a broken section on a
        // live marketing page.
        host.innerHTML = "";
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
