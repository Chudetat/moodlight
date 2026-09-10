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

    // Each sentence is its own inline-block, so a narrow screen breaks BETWEEN
    // the two sentences instead of orphaning "What" at the end of line one.
    // clamp() lets the type shrink on a phone rather than forcing the wrap.
    var h2 = el("h2",
      "font-size:clamp(22px,6vw,30px);font-weight:600;margin:12px 0 10px;line-height:1.25;");
    h2.appendChild(el("span", "display:inline-block;", "What we predicted."));
    h2.appendChild(document.createTextNode(" "));
    h2.appendChild(el("span", "display:inline-block;", "What actually happened."));
    root.appendChild(h2);
    root.appendChild(el("p",
      "font-size:16px;line-height:1.6;color:#3C4453;margin:0 0 6px;",
      "Every call is dated and the evidence is sealed the moment it is made. " +
      "Including the ones we get wrong."));

    var tally = Object.keys(data.counts || {}).map(function (k) {
      return (VERDICT[k] ? VERDICT[k][0].toLowerCase() : k) + " " + data.counts[k];
    }).join("  ·  ") || "none resolved yet";
    root.appendChild(el("p",
      "font-size:14px;line-height:1.6;color:#5A616E;margin:0 0 36px;",
      data.total + " calls  ·  " + data.open + " still open  ·  " + tally));

    // Capped on purpose. The weekly proposer adds up to three calls a week, so
    // uncapped this is ~46 calls by December and 150+ within a year - at which
    // point it is the page rather than a section on it, and the marketplace
    // below never gets seen. The full record lives at /predictions.
    var SHOW_OPEN = 4, SHOW_DONE = 4;

    // Soonest to resolve first: "resolves next week" is a live bet a reader can
    // come back and check, while one due in four months is not yet interesting.
    var openCalls = data.calls.filter(function (c) { return !c.status; })
      .sort(function (a, b) { return (a.due || "") < (b.due || "") ? -1 : 1; });
    // Newest first, so the freshest evidence is the evidence on show.
    var done = data.calls.filter(function (c) { return c.status; });

    if (openCalls.length) {
      root.appendChild(el("h3",
        "font-size:13px;letter-spacing:.14em;text-transform:uppercase;color:#5A616E;" +
        "font-weight:700;margin:0 0 4px;", "Open — outcome not yet known"));
      openCalls.slice(0, SHOW_OPEN).forEach(function (c) { root.appendChild(card(c)); });
    }
    if (done.length) {
      root.appendChild(el("h3",
        "font-size:13px;letter-spacing:.14em;text-transform:uppercase;color:#5A616E;" +
        "font-weight:700;margin:44px 0 4px;", "Resolved"));
      done.slice(0, SHOW_DONE).forEach(function (c) { root.appendChild(card(c)); });
    }

    if (data.total > SHOW_OPEN + SHOW_DONE) {
      var more = el("a",
        "display:inline-block;margin-top:26px;color:#C57A11;font-size:14px;" +
        "font-weight:600;text-decoration:none;border-bottom:1px solid #C57A11;" +
        "padding-bottom:2px;", "See all " + data.total + " calls \u203A");
      more.href = API + "/predictions";
      more.target = "_blank";
      more.rel = "noopener";
      root.appendChild(more);
    }

    root.appendChild(el("p",
      "font-size:13px;color:#6B7280;margin-top:36px;line-height:1.6;",
      "Calls are recorded before their outcome is known and the supporting evidence "  +
      "is hashed at the moment each one is made. Resolution is a human judgement, " +
      "never the engine grading itself."));
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
