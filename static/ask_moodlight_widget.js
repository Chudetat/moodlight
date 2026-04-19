/**
 * Ask Moodlight — Embeddable Intelligence Widget
 * Google-style clean interface with Moodlight branding.
 *
 * Usage (inline — recommended for sales site):
 *   <div id="ask-moodlight-embed"></div>
 *   <script src="https://your-api-domain.up.railway.app/static/ask_moodlight_widget.js"
 *           data-mode="inline" data-target="ask-moodlight-embed"></script>
 *
 * Usage (floating chat bubble):
 *   <script src="https://your-api-domain.up.railway.app/static/ask_moodlight_widget.js"></script>
 */

(function () {
  "use strict";

  const scriptTag = document.currentScript;
  const scriptSrc = scriptTag ? scriptTag.src : "";
  const API_BASE = scriptSrc
    ? scriptSrc.replace(/\/static\/ask_moodlight_widget\.js.*$/, "")
    : "https://ask-moodlight.up.railway.app";
  const MODE = scriptTag?.getAttribute("data-mode") || "floating";
  const TARGET = scriptTag?.getAttribute("data-target") || null;

  let conversation = [];
  let isOpen = false;
  let queriesRemaining = 999;
  let hasSearched = false;
  let paidToken = localStorage.getItem("ml_paid_token") || null;
  let isPaid = false;

  // Check for Stripe redirect (ml_session in URL)
  const urlParams = new URLSearchParams(window.location.search);
  const mlSession = urlParams.get("ml_session");
  if (mlSession) {
    // Activate the token
    fetch(API_BASE + "/api/activate?session_id=" + encodeURIComponent(mlSession))
      .then((r) => r.json())
      .then((data) => {
        if (data.token) {
          paidToken = data.token;
          isPaid = true;
          queriesRemaining = data.queries_remaining;
          localStorage.setItem("ml_paid_token", data.token);
          // Clean URL
          const clean = window.location.href.split("?")[0];
          window.history.replaceState({}, "", clean);
          updateBadge();
        }
      })
      .catch(() => {});
  }

  // If we have a stored token, validate it
  if (paidToken && !mlSession) {
    isPaid = true;
    queriesRemaining = 10; // Will be corrected on first API response
  }

  // ── Styles ──
  const STYLES = `
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&display=swap');

    /* ── Floating button ── */
    #ml-widget-btn {
      position: fixed;
      bottom: 24px;
      right: 24px;
      width: 60px;
      height: 60px;
      border-radius: 50%;
      background: linear-gradient(135deg, #6B46C1, #1976D2);
      border: none;
      cursor: pointer;
      box-shadow: 0 4px 20px rgba(107, 70, 193, 0.4);
      z-index: 10000;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: transform 0.2s, box-shadow 0.2s;
    }
    #ml-widget-btn:hover {
      transform: scale(1.08);
      box-shadow: 0 6px 28px rgba(107, 70, 193, 0.5);
    }
    #ml-widget-btn svg { width: 28px; height: 28px; }
    #ml-widget-btn img { width: 36px; height: 36px; }

    /* ── Floating panel ── */
    #ml-widget-panel.floating-mode {
      position: fixed;
      bottom: 96px;
      right: 24px;
      width: 400px;
      max-height: 560px;
      background: #FFFFFF;
      border: 1px solid rgba(0, 0, 0, 0.1);
      border-radius: 16px;
      box-shadow: 0 8px 40px rgba(0, 0, 0, 0.15);
      z-index: 10001;
      display: none;
      flex-direction: column;
      overflow: hidden;
      font-family: 'Space Grotesk', sans-serif;
    }
    #ml-widget-panel.floating-mode.open { display: flex; }

    /* ── Inline mode (Google-style) ── */
    #ml-widget-panel.inline-mode {
      position: relative;
      width: 100%;
      max-width: 720px;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      align-items: center;
      font-family: 'Space Grotesk', sans-serif;
      padding: 12px 20px;
    }

    /* ── Logo area ── */
    .ml-logo {
      text-align: center;
      padding: 6px 0 18px 0;
    }
    .ml-logo-text {
      font-size: 56px;
      font-weight: 400;
      color: #2D2D2D;
      font-family: 'Space Grotesk', sans-serif;
      letter-spacing: -0.5px;
      line-height: 1.1;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 14px;
    }
    .ml-logo-icon {
      font-size: 48px;
    }
    .ml-logo-sub {
      font-size: 15px;
      color: rgba(45, 45, 45, 0.5);
      font-weight: 300;
      margin-top: 8px;
      letter-spacing: 0.5px;
    }

    /* ── Search bar (Google-style) ── */
    .ml-search-container {
      width: 100%;
      max-width: 580px;
      position: relative;
      margin: 0 auto;
    }
    .ml-search-bar {
      width: 100%;
      background: rgba(0, 0, 0, 0.04);
      border: 1px solid rgba(0, 0, 0, 0.12);
      border-radius: 28px;
      padding: 16px 56px 16px 24px;
      color: #2D2D2D;
      font-size: 16px;
      font-family: 'Space Grotesk', sans-serif;
      outline: none;
      transition: border-color 0.3s, box-shadow 0.3s, background 0.3s;
      box-sizing: border-box;
    }
    .ml-search-bar::placeholder {
      color: rgba(45, 45, 45, 0.65);
      font-weight: 400;
    }
    .ml-search-bar:focus {
      border-color: rgba(107, 70, 193, 0.5);
      box-shadow: 0 4px 24px rgba(107, 70, 193, 0.15);
      background: rgba(0, 0, 0, 0.02);
    }
    .ml-search-bar:disabled { opacity: 0.5; }

    .ml-search-btn {
      position: absolute;
      right: 6px;
      top: 50%;
      transform: translateY(-50%);
      width: 42px;
      height: 42px;
      border-radius: 50%;
      background: linear-gradient(135deg, #6B46C1, #1976D2);
      border: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: opacity 0.2s, transform 0.2s;
    }
    .ml-search-btn:hover { opacity: 0.85; transform: translateY(-50%) scale(1.05); }
    .ml-search-btn:disabled { opacity: 0.3; cursor: not-allowed; transform: translateY(-50%); }
    .ml-search-btn svg { width: 18px; height: 18px; fill: white; }

    /* ── Suggested prompts ── */
    .ml-prompts {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin-top: 16px;
      width: 100%;
      max-width: 580px;
    }
    .ml-prompt-chip {
      background: rgba(0, 0, 0, 0.04);
      border: 1px solid rgba(0, 0, 0, 0.12);
      border-radius: 12px;
      padding: 10px 16px;
      font-size: 13px;
      line-height: 1.4;
      color: rgba(45, 45, 45, 0.8);
      cursor: pointer;
      transition: all 0.2s;
      font-family: 'Space Grotesk', sans-serif;
      text-align: left;
    }
    .ml-prompt-chip:hover {
      background: rgba(0, 0, 0, 0.08);
      border-color: rgba(0, 0, 0, 0.18);
      color: #2D2D2D;
    }

    /* ── Results area ── */
    .ml-results {
      width: 100%;
      max-width: 580px;
      margin-top: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      max-height: 300px;
      overflow-y: auto;
    }
    .ml-results::-webkit-scrollbar { width: 4px; }
    .ml-results::-webkit-scrollbar-track { background: transparent; }
    .ml-results::-webkit-scrollbar-thumb { background: rgba(0, 0, 0, 0.15); border-radius: 2px; }

    .ml-result-user {
      font-size: 14px;
      color: rgba(45, 45, 45, 0.6);
      padding: 0 4px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .ml-result-user-icon {
      width: 24px;
      height: 24px;
      border-radius: 50%;
      background: linear-gradient(135deg, #6B46C1, #1976D2);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 11px;
      color: white;
      flex-shrink: 0;
    }

    .ml-result-card {
      background: rgba(0, 0, 0, 0.03);
      border: 1px solid rgba(0, 0, 0, 0.08);
      border-radius: 12px;
      padding: 16px 20px;
      color: #3D3D3D;
      font-size: 14px;
      line-height: 1.6;
      word-wrap: break-word;
    }
    .ml-result-card strong { color: #1A1A1A; }
    .ml-result-card p { margin: 8px 0; }

    /* ── Typing indicator ── */
    .ml-typing-bar {
      display: flex;
      gap: 5px;
      padding: 20px 24px;
      background: rgba(0, 0, 0, 0.03);
      border: 1px solid rgba(0, 0, 0, 0.08);
      border-radius: 12px;
    }
    .ml-typing-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: rgba(107, 70, 193, 0.5);
      animation: mlBounce 1.4s infinite ease-in-out both;
    }
    .ml-typing-dot:nth-child(1) { animation-delay: -0.32s; }
    .ml-typing-dot:nth-child(2) { animation-delay: -0.16s; }
    @keyframes mlBounce {
      0%, 80%, 100% { transform: scale(0); }
      40% { transform: scale(1); }
    }

    /* ── Badge ── */
    .ml-queries-badge {
      font-size: 12px;
      color: rgba(45, 45, 45, 0.65);
      text-align: center;
      margin-top: 12px;
    }

    /* ── New question button ── */
    .ml-new-question {
      text-align: center;
      margin-top: 12px;
    }
    .ml-new-question-btn {
      background: none;
      border: 1px solid rgba(0, 0, 0, 0.12);
      border-radius: 20px;
      padding: 8px 20px;
      font-size: 13px;
      color: rgba(45, 45, 45, 0.5);
      cursor: pointer;
      font-family: 'Space Grotesk', sans-serif;
      transition: all 0.2s;
    }
    .ml-new-question-btn:hover {
      border-color: rgba(0, 0, 0, 0.25);
      color: #2D2D2D;
    }

    /* ── Agent marketplace CTA ── */
    .ml-agent-cta {
      margin: 16px 0 4px 0;
      padding: 14px 16px;
      background: linear-gradient(135deg, rgba(107, 70, 193, 0.06), rgba(25, 118, 210, 0.06));
      border: 1px solid rgba(107, 70, 193, 0.18);
      border-radius: 14px;
    }
    .ml-agent-cta-label {
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: rgba(45, 45, 45, 0.55);
      margin-bottom: 6px;
    }
    .ml-agent-cta-name {
      font-size: 15px;
      font-weight: 600;
      color: #2D2D2D;
      margin-bottom: 6px;
      font-family: 'Space Grotesk', sans-serif;
    }
    .ml-agent-cta-why {
      font-size: 13px;
      color: rgba(45, 45, 45, 0.75);
      line-height: 1.5;
      margin-bottom: 6px;
    }
    .ml-agent-cta-deliverable {
      font-size: 12px;
      color: rgba(45, 45, 45, 0.6);
      line-height: 1.45;
      margin-bottom: 12px;
      font-style: italic;
    }
    .ml-agent-cta-btn {
      display: inline-block;
      background: linear-gradient(135deg, #6B46C1, #1976D2);
      color: white;
      border: none;
      border-radius: 20px;
      padding: 10px 22px;
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      font-family: 'Space Grotesk', sans-serif;
      transition: opacity 0.2s, transform 0.2s;
      text-decoration: none;
    }
    .ml-agent-cta-btn:hover {
      opacity: 0.9;
      transform: scale(1.02);
    }
    .ml-agent-cta-workflow {
      margin-top: 14px;
      padding-top: 14px;
      border-top: 1px dashed rgba(107, 70, 193, 0.22);
    }
    .ml-agent-cta-workflow-label {
      font-size: 11px;
      font-weight: 600;
      color: #6B46C1;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 8px;
    }
    .ml-agent-cta-workflow-ladder {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 6px 4px;
      margin-bottom: 8px;
    }
    .ml-workflow-step {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: rgba(107, 70, 193, 0.08);
      border: 1px solid rgba(107, 70, 193, 0.20);
      color: #5a1480;
      border-radius: 999px;
      padding: 5px 12px 5px 8px;
      font-size: 12px;
      font-weight: 500;
      font-family: 'Space Grotesk', sans-serif;
      cursor: pointer;
      transition: background 0.15s, transform 0.15s;
    }
    .ml-workflow-step:hover {
      background: rgba(107, 70, 193, 0.14);
      transform: translateY(-1px);
    }
    .ml-workflow-step-num {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 18px;
      height: 18px;
      border-radius: 50%;
      background: #6B46C1;
      color: white;
      font-size: 10px;
      font-weight: 700;
    }
    .ml-workflow-arrow {
      color: rgba(107, 70, 193, 0.5);
      font-size: 12px;
      padding: 0 1px;
    }
    .ml-agent-cta-workflow-reasoning {
      font-size: 11px;
      color: rgba(45, 45, 45, 0.6);
      line-height: 1.5;
      font-style: italic;
    }

    /* ── Unlock button ── */
    .ml-unlock-btn {
      display: inline-block;
      background: linear-gradient(135deg, #6B46C1, #1976D2);
      color: white;
      border: none;
      border-radius: 24px;
      padding: 12px 28px;
      font-size: 14px;
      font-weight: 500;
      font-family: 'Space Grotesk', sans-serif;
      cursor: pointer;
      transition: opacity 0.2s, transform 0.2s;
      margin-top: 8px;
    }
    .ml-unlock-btn:hover {
      opacity: 0.9;
      transform: scale(1.02);
    }
    .ml-unlock-cta {
      text-align: center;
      margin-top: 16px;
    }
    .ml-unlock-cta p {
      color: rgba(45, 45, 45, 0.5);
      font-size: 13px;
      margin: 0 0 8px 0;
    }

    /* ── Footer ── */
    .ml-footer-inline {
      margin-top: 16px;
      text-align: center;
      font-size: 11px;
      color: rgba(45, 45, 45, 0.35);
    }
    .ml-footer-inline a {
      color: rgba(45, 45, 45, 0.45);
      text-decoration: none;
    }
    .ml-footer-inline a:hover { color: rgba(45, 45, 45, 0.7); }

    /* ── Floating panel header ── */
    .ml-float-header {
      padding: 14px 20px;
      background: linear-gradient(135deg, rgba(107, 70, 193, 0.06), rgba(25, 118, 210, 0.04));
      border-bottom: 1px solid rgba(0, 0, 0, 0.08);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .ml-float-header-title {
      font-size: 14px;
      font-weight: 600;
      color: #2D2D2D;
    }
    .ml-float-close {
      background: none;
      border: none;
      color: rgba(45, 45, 45, 0.4);
      cursor: pointer;
      font-size: 20px;
      padding: 0;
      line-height: 1;
    }
    .ml-float-close:hover { color: #2D2D2D; }

    /* ── Responsive ── */
    @media (max-width: 640px) {
      .ml-logo-text { font-size: 32px; }
      .ml-search-bar { font-size: 14px; padding: 14px 50px 14px 20px; }
      .ml-search-btn { width: 36px; height: 36px; }
      .ml-result-card { padding: 16px; font-size: 13px; }
      #ml-widget-panel.inline-mode { padding: 12px; }
    }
  `;

  const styleEl = document.createElement("style");
  styleEl.textContent = STYLES;
  document.head.appendChild(styleEl);

  // ── Render ──
  function renderWidget() {
    if (MODE === "inline" && TARGET) {
      renderInline();
    } else {
      renderFloating();
    }
  }

  function renderFloating() {
    const btn = document.createElement("button");
    btn.id = "ml-widget-btn";
    btn.innerHTML = '<img src="' + API_BASE + '/static/logo_white.png" alt="Moodlight">';
    btn.title = "Ask Moodlight";
    btn.onclick = togglePanel;
    document.body.appendChild(btn);

    const panel = document.createElement("div");
    panel.id = "ml-widget-panel";
    panel.classList.add("floating-mode");
    panel.innerHTML = `
      <div class="ml-float-header">
        <div class="ml-float-header-title">Ask Moodlight</div>
        <button class="ml-float-close" onclick="document.getElementById('ml-widget-panel').classList.remove('open')">&times;</button>
      </div>
      <div style="flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column;">
        <div class="ml-logo" style="padding: 8px 0 16px 0;">
          <div class="ml-logo-text" style="font-size: 28px;"><img src="${API_BASE}/static/logo_black.png" alt="Moodlight" style="width:32px;height:32px;vertical-align:middle;margin-right:8px;">Moodlight</div>
        </div>
        <div class="ml-search-container">
          <input class="ml-search-bar" id="ml-input" type="text"
                 placeholder="Ask about any brand, trend, or strategy..."
                 maxlength="500" style="font-size: 14px; padding: 12px 48px 12px 18px;"
                 onkeydown="if(event.key==='Enter')window._mlSend()">
          <button class="ml-search-btn" id="ml-send-btn" onclick="window._mlSend()" style="width: 36px; height: 36px;">
            <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
          </button>
        </div>
        <div class="ml-results" id="ml-messages" style="margin-top: 16px; max-height: 280px;"></div>
      </div>
    `;
    document.body.appendChild(panel);
  }

  function renderInline() {
    const target = document.getElementById(TARGET);
    if (!target) return;

    const panel = document.createElement("div");
    panel.id = "ml-widget-panel";
    panel.classList.add("inline-mode");

    // Rotating prompt pools — one prompt picked from each slot on load
    // so visitors see different agents across the 26-agent marketplace
    const promptPools = [
      [
        "Build a Chief Creative Officer brief for Nike",
        "Build a Cultural Strategist brief for Airbnb",
        "Build a Comms Planner brief for a Peloton relaunch",
        "Build a Full Deploy brief for Liquid Death",
        "Build a Data Strategist brief for Allbirds",
        "Build a Creative Technologist brief for Nothing",
        "Build a Partnership Scout brief for Patagonia",
        "Build a Referral Architect brief for Hims",
        "Build a Paid Media Strategist brief for Allbirds",
        "Build a Lifecycle Strategist brief for a subscription box",
        "Build a Global Creative Council entry strategy for our Cannes case study",
        "Build a Focus Group gut check on a new tagline",
        "Build a Trend Forecaster brief for Rhode",
        "Build a Pitch Builder deck for a new business win",
        "Build a Crisis Advisor brief for Boeing",
        "Build a Copywriter brief for a DTC product launch",
      ],
      [
        "What's the cultural read on Microsoft right now?",
        "What's shifting in Gen Z attention right now?",
        "Where is the conversation moving on AI and labor?",
        "What's the mood around luxury brands right now?",
        "What's breaking in the creator economy this week?",
        "What's the read on Gen Alpha vs Gen Z right now?",
      ],
      [
        "Run a Brand Audit on Netflix",
        "Run a Competitive Scout on Spotify",
        "Run an Audience Profiler on Peloton",
        "Run a Content Strategist on Glossier",
        "Run a Social Strategist on Duolingo",
        "Run a Funnel Doctor on a DTC checkout flow",
        "Run an Experimentation Strategist on a landing page test",
        "Run a Culture Translator on a brand entering Japan",
        "Run a Focus Group on a pre-launch creative concept",
        "Run a Global Creative Council on a case study headed to Cannes",
        "Run a Brief Critic on a client brief",
        "Run a SEO Strategist on Patagonia",
      ],
    ];
    const suggestedPrompts = promptPools.map(
      (pool) => pool[Math.floor(Math.random() * pool.length)]
    );

    panel.innerHTML = `
      <div class="ml-search-container">
        <input class="ml-search-bar" id="ml-input" type="text"
               placeholder="Ask about any brand, trend, or strategy..."
               maxlength="500"
               onkeydown="if(event.key==='Enter')window._mlSend()">
        <button class="ml-search-btn" id="ml-send-btn" onclick="window._mlSend()">
          <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
        </button>
      </div>

      <div class="ml-prompts" id="ml-prompts">
        ${suggestedPrompts.map((p) => `<div class="ml-prompt-chip" onclick="window._mlAsk(this.dataset.prompt)" data-prompt="${p.replace(/"/g, '&quot;')}">${p}</div>`).join("")}
      </div>

      <div class="ml-results" id="ml-messages"></div>

    `;

    target.appendChild(panel);
  }

  function togglePanel() {
    const panel = document.getElementById("ml-widget-panel");
    if (panel) {
      isOpen = !isOpen;
      panel.classList.toggle("open", isOpen);
      if (isOpen) {
        setTimeout(() => document.getElementById("ml-input")?.focus(), 100);
      }
    }
  }

  // ── Chat logic ──
  window._mlAsk = function (promptOrEl) {
    const input = document.getElementById("ml-input");
    if (input) {
      input.value = typeof promptOrEl === "string" ? promptOrEl : promptOrEl;
      window._mlSend();
    }
  };

  window._mlSend = async function () {
    const input = document.getElementById("ml-input");
    const sendBtn = document.getElementById("ml-send-btn");
    const messages = document.getElementById("ml-messages");
    if (!input || !messages) return;

    const question = input.value.trim();
    if (!question) return;
    if (queriesRemaining <= 0 && !isPaid) {
      showUnlockPrompt(messages);
      return;
    }
    if (queriesRemaining <= 0 && isPaid) {
      addResult(messages, "assistant", "You've used all your purchased questions. Grab another pack to keep going.");
      showUnlockPrompt(messages);
      return;
    }

    // Hide suggested prompts after first search
    if (!hasSearched) {
      hasSearched = true;
      const prompts = document.getElementById("ml-prompts");
      if (prompts) prompts.style.display = "none";
    }

    // Add user query
    addResult(messages, "user", question);
    input.value = "";
    input.disabled = true;
    sendBtn.disabled = true;

    // Typing indicator
    const typing = document.createElement("div");
    typing.className = "ml-typing-bar";
    typing.innerHTML = '<div class="ml-typing-dot"></div><div class="ml-typing-dot"></div><div class="ml-typing-dot"></div>';
    messages.appendChild(typing);
    messages.scrollTop = messages.scrollHeight;

    try {
      const res = await fetch(API_BASE + "/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question, conversation, token: paidToken,
          email: (function () { try { return localStorage.getItem("ml_team_email") || undefined; } catch (e) { return undefined; } })(),
        }),
      });

      typing.remove();

      if (!res.ok) {
        addResult(messages, "assistant", "Something went wrong. Please try again.");
        return;
      }

      const data = await res.json();
      conversation.push({ role: "user", content: question });
      conversation.push({ role: "assistant", content: data.answer });
      queriesRemaining = data.queries_remaining;
      if (data.is_paid) isPaid = true;
      updateBadge();

      addResult(messages, "assistant", data.answer);

      // Persist brief fields immediately so the marketplace can
      // auto-fill even if the user scrolls down manually instead
      // of clicking the CTA button.
      if (data.brief_fields || data.detected_brand || data.question) {
        var earlyFields = (data.brief_fields) ? Object.assign({}, data.brief_fields) : {};
        if (!earlyFields.product && data.detected_brand) earlyFields.product = data.detected_brand;
        if (!earlyFields.challenge && data.question) earlyFields.challenge = data.question;
        window._mlParsedBriefFields = earlyFields;
        try {
          localStorage.setItem("ml_active_brief", JSON.stringify({
            fields: earlyFields,
            originalQuestion: data.question || "",
            detectedBrand: data.detected_brand || "",
            recommendedAgent: (data.recommended_agent && data.recommended_agent.id) || "",
            timestamp: Date.now(),
          }));
        } catch (e) {}
      }

      // Always attempt to show the handoff CTA. The backend emits a
      // structured `recommended_agent` on every answer now; if it's
      // missing we fall back to a generic brand-auditor nudge.
      showAgentCta(messages, data);
      showNewQuestionBtn(messages);
    } catch (err) {
      typing.remove();
      addResult(messages, "assistant", "Connection error. Please try again.");
    } finally {
      input.disabled = false;
      sendBtn.disabled = false;
      input.placeholder = "Follow up, or ask Moodlight to build a brief for a specific agent...";
      input.focus();
    }
  };

  function showNewQuestionBtn(container) {
    const existing = container.querySelector(".ml-new-question");
    if (existing) existing.remove();
    const el = document.createElement("div");
    el.className = "ml-new-question";
    el.innerHTML = '<button class="ml-new-question-btn" onclick="window._mlClear()">Ask a new question</button>';
    container.appendChild(el);
    container.scrollTop = container.scrollHeight;
  }

  // Display title lookup for every marketplace agent — keyed by the
  // same IDs the backend emits in its <moodlight-route> block. Keep
  // this in sync with static/agent_marketplace.js AGENTS[].
  var AGENT_TITLES = {
    "new-business-win": "New Business Win",
    "outbound-discovery": "Outbound Discovery",
    "cco": "The Chief Creative Officer",
    "cso": "The Cultural Strategist",
    "comms-planner": "The Comms Planner",
    "full-deploy": "Full Deploy",
    "data-strategist": "The Data Strategist",
    "creative-technologist": "The Creative Technologist",
    "brand-auditor": "The Brand Auditor",
    "brief-critic": "The Brief Critic",
    "trend-forecaster": "The Trend Forecaster",
    "copywriter": "The Copywriter",
    "crisis-advisor": "The Crisis Advisor",
    "audience-profiler": "The Audience Profiler",
    "competitive-scout": "The Competitive Scout",
    "partnership-scout": "The Partnership Scout",
    "pitch-builder": "The Pitch Builder",
    "pitch-strategist": "The Pitch Strategist",
    "content-strategist": "The Content Strategist",
    "culture-translator": "The Culture Translator",
    "social-strategist": "The Social Strategist",
    "gtm-researcher": "The GTM Researcher",
    "seo-strategist": "The SEO Strategist",
    "paid-media-strategist": "The Paid Media Strategist",
    "funnel-doctor": "The Funnel Doctor",
    "lifecycle-strategist": "The Lifecycle Strategist",
    "experimentation-strategist": "The Experimentation Strategist",
    "referral-architect": "The Referral Architect",
    "creative-council": "The Global Creative Council",
    "focus-group": "The Focus Group",
    "bill-bernbach": "Bill Bernbach",
    "david-ogilvy": "David Ogilvy",
  };

  function showAgentCta(container, data) {
    const existing = container.querySelector(".ml-agent-cta");
    if (existing) existing.remove();

    // If the question matched a saved team, show a team CTA instead
    var team = data && data.recommended_team;
    if (team && team.id && team.agent_sequence && team.agent_sequence.length >= 2) {
      var teamEl = document.createElement("div");
      teamEl.className = "ml-agent-cta";

      var teamLabel = document.createElement("div");
      teamLabel.className = "ml-agent-cta-label";
      teamLabel.textContent = "Your team \u2192";
      teamEl.appendChild(teamLabel);

      var teamName = document.createElement("div");
      teamName.className = "ml-agent-cta-name";
      teamName.textContent = team.name;
      teamEl.appendChild(teamName);

      // Show the agent sequence as a mini ladder
      var seqText = (team.agent_labels || []).map(function (a, i) {
        return (i + 1) + ". " + a.name;
      }).join("  \u2192  ");
      var seqEl = document.createElement("div");
      seqEl.className = "ml-agent-cta-why";
      seqEl.textContent = seqText;
      teamEl.appendChild(seqEl);

      // Use structured brief fields extracted by the backend (Haiku)
      // instead of dumping the raw question into form fields
      var detectedBrand = (data && data.detected_brand) || "";
      var rawQuestion = (data && data.question) || "";
      var parsedFields = (data && data.brief_fields) || {};
      if (!parsedFields.product && detectedBrand) parsedFields.product = detectedBrand;

      var teamBtn = document.createElement("button");
      teamBtn.className = "ml-agent-cta-btn";
      teamBtn.textContent = "Run " + team.name + " \u2193";
      teamBtn.onclick = function () {
        window._mlParsedBriefFields = parsedFields;
        try {
          localStorage.setItem("ml_active_brief", JSON.stringify({
            fields: parsedFields,
            originalQuestion: rawQuestion,
            detectedBrand: detectedBrand,
            recommendedAgent: team.agent_sequence[0],
            timestamp: Date.now(),
          }));
          localStorage.setItem("ml_team_handoff", JSON.stringify({
            id: team.id,
            name: team.name,
            agent_sequence: team.agent_sequence,
            timestamp: Date.now(),
          }));
        } catch (e) {}
        var marketplace = document.getElementById("ml-marketplace") || document.getElementById("moodlight-marketplace");
        if (marketplace) {
          marketplace.scrollIntoView({ behavior: "smooth", block: "start" });
          setTimeout(function () {
            if (window._mlRunTeamHandoff) window._mlRunTeamHandoff();
          }, 600);
        }
      };
      teamEl.appendChild(teamBtn);

      container.appendChild(teamEl);
      container.scrollTop = container.scrollHeight;
      return;  // Team CTA takes priority — don't show single-agent CTA
    }

    // Prefer the structured handoff from the backend. Fall back to
    // brand-auditor so every answer still offers a next move.
    var rec = data && data.recommended_agent;
    var agentId = rec && rec.id && AGENT_TITLES[rec.id] ? rec.id : "brand-auditor";
    var agentName = AGENT_TITLES[agentId];
    var why = (rec && rec.why) || "";
    var deliverable = (rec && rec.deliverable) || "";

    // Use structured brief fields from the backend (Haiku extraction)
    // when available. Fall back to inline regex parsing, then raw
    // brand/question as last resort.
    var parsedFields = (data && data.brief_fields) ? Object.assign({}, data.brief_fields) : {};
    var answer = (data && data.answer) || "";
    if (!parsedFields.product || !parsedFields.challenge) {
      var fieldPatterns = {
        product: /\*\*Product\/Service:\*\*\s*(.+)/i,
        audience: /\*\*Target Audience:\*\*\s*(.+)/i,
        markets: /\*\*Markets\/Geography:\*\*\s*(.+)/i,
        challenge: /\*\*Key Challenge:\*\*\s*(.+)/i,
        timeline: /\*\*Timeline\/Budget:\*\*\s*(.+)/i,
      };
      for (var key in fieldPatterns) {
        if (!parsedFields[key]) {
          var m = answer.match(fieldPatterns[key]);
          if (m) parsedFields[key] = m[1].trim();
        }
      }
    }

    var detectedBrand = (data && data.detected_brand) || "";
    var rawQuestion = (data && data.question) || "";
    if (!parsedFields.product && detectedBrand) {
      parsedFields.product = detectedBrand;
    }
    if (!parsedFields.challenge && rawQuestion) {
      parsedFields.challenge = rawQuestion;
    }

    // Build the CTA card
    var el = document.createElement("div");
    el.className = "ml-agent-cta";

    var label = document.createElement("div");
    label.className = "ml-agent-cta-label";
    label.textContent = "Your next move \u2192";
    el.appendChild(label);

    var nameEl = document.createElement("div");
    nameEl.className = "ml-agent-cta-name";
    nameEl.textContent = agentName;
    el.appendChild(nameEl);

    if (why) {
      var whyEl = document.createElement("div");
      whyEl.className = "ml-agent-cta-why";
      whyEl.textContent = why;
      el.appendChild(whyEl);
    }

    if (deliverable) {
      var delEl = document.createElement("div");
      delEl.className = "ml-agent-cta-deliverable";
      delEl.textContent = "You'll get: " + deliverable;
      el.appendChild(delEl);
    }

    // Shared handoff — persist brief to localStorage and click the
    // target marketplace agent card. Used by both the primary CTA
    // button and every step chip in the workflow ladder.
    function handoffTo(targetAgentId, targetAgentName) {
      window._mlParsedBriefFields = parsedFields;
      try {
        localStorage.setItem("ml_active_brief", JSON.stringify({
          fields: parsedFields,
          originalQuestion: rawQuestion,
          detectedBrand: detectedBrand,
          recommendedAgent: targetAgentId,
          timestamp: Date.now(),
        }));
      } catch (e) {}

      var marketplace = document.getElementById("ml-marketplace") || document.getElementById("moodlight-marketplace");
      if (!marketplace) return;

      marketplace.scrollIntoView({ behavior: "smooth", block: "start" });
      setTimeout(function () {
        var cards = marketplace.querySelectorAll(".ml-agent-card");
        cards.forEach(function (card) {
          var title = card.querySelector("h3");
          if (title && title.textContent.trim() === targetAgentName) {
            card.click();
          }
        });
      }, 500);
    }

    var btn = document.createElement("button");
    btn.className = "ml-agent-cta-btn";
    btn.textContent = "Run " + agentName + " \u2193";
    btn.onclick = function () { handoffTo(agentId, agentName); };
    el.appendChild(btn);

    // Ship 3: Moodlight Methodology workflow ladder. When Claude
    // emits a multi-step sequence, render it as numbered clickable
    // chips below the primary CTA so the user can see the full
    // recommended workflow and jump directly to any step. Ship 2
    // upstream context automatically links them together when the
    // user runs them in order.
    var sequence = (rec && Array.isArray(rec.sequence)) ? rec.sequence : [];
    if (sequence.length >= 2) {
      var workflow = document.createElement("div");
      workflow.className = "ml-agent-cta-workflow";

      var workflowLabel = document.createElement("div");
      workflowLabel.className = "ml-agent-cta-workflow-label";
      workflowLabel.textContent = "The Moodlight Methodology \u2192";
      workflow.appendChild(workflowLabel);

      var ladder = document.createElement("div");
      ladder.className = "ml-agent-cta-workflow-ladder";
      sequence.forEach(function (step, idx) {
        if (idx > 0) {
          var arrow = document.createElement("span");
          arrow.className = "ml-workflow-arrow";
          arrow.textContent = "\u2192";
          ladder.appendChild(arrow);
        }
        var chip = document.createElement("button");
        chip.className = "ml-workflow-step";
        chip.type = "button";
        var num = document.createElement("span");
        num.className = "ml-workflow-step-num";
        num.textContent = String(idx + 1);
        chip.appendChild(num);
        var chipLabel = document.createElement("span");
        chipLabel.textContent = step.name || step.id;
        chip.appendChild(chipLabel);
        chip.onclick = function () { handoffTo(step.id, step.name || step.id); };
        ladder.appendChild(chip);
      });
      workflow.appendChild(ladder);

      var seqWhy = (rec && rec.sequence_reasoning) || "";
      if (seqWhy) {
        var reasoningEl = document.createElement("div");
        reasoningEl.className = "ml-agent-cta-workflow-reasoning";
        reasoningEl.textContent = seqWhy;
        workflow.appendChild(reasoningEl);
      }

      el.appendChild(workflow);
    }

    container.appendChild(el);
    container.scrollTop = container.scrollHeight;
  }

  window._mlClear = function () {
    conversation = [];
    const messages = document.getElementById("ml-messages");
    if (messages) messages.innerHTML = "";
    const input = document.getElementById("ml-input");
    if (input) {
      input.value = "";
      input.placeholder = "Ask about any brand, trend, or strategy...";
      input.focus();
    }
  };

  function showUnlockPrompt(container) {
    const existing = container.querySelector(".ml-unlock-cta");
    if (existing) return; // Don't show twice
    const el = document.createElement("div");
    el.className = "ml-unlock-cta";
    el.innerHTML = `
      <p>You've used your free questions for today.</p>
      <button class="ml-unlock-btn" onclick="window._mlUnlock()">Unlock 10 more questions — $10</button>
    `;
    container.appendChild(el);
    container.scrollTop = container.scrollHeight;
  }

  window._mlUnlock = async function () {
    try {
      const res = await fetch(API_BASE + "/api/checkout", { method: "POST" });
      const data = await res.json();
      if (data.url) {
        window.location.href = data.url;
      }
    } catch (err) {
      console.error("Checkout error:", err);
    }
  };

  function addResult(container, role, text) {
    if (role === "user") {
      const el = document.createElement("div");
      el.className = "ml-result-user";
      el.innerHTML = `<div class="ml-result-user-icon">Q</div> ${escapeHtml(text)}`;
      container.appendChild(el);
    } else {
      const el = document.createElement("div");
      el.className = "ml-result-card";
      // Markdown rendering: bold, italic, line breaks, bullet lists
      el.innerHTML = text
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.*?)\*/g, "<em>$1</em>")
        .replace(/^- (.*)/gm, "<li>$1</li>")
        .replace(/(<li>.*<\/li>)/gs, "<ul>$1</ul>")
        .replace(/<\/ul>\s*<ul>/g, "")
        .replace(/\n\n/g, "</p><p>")
        .replace(/\n/g, "<br>");
      container.appendChild(el);
    }
    container.scrollTop = container.scrollHeight;
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function updateBadge() {
    const badge = document.getElementById("ml-queries-badge");
    if (badge) {
      if (queriesRemaining > 0) {
        const label = isPaid ? "question" : "free question";
        badge.textContent = `${queriesRemaining} ${label}${queriesRemaining !== 1 ? "s" : ""} remaining`;
      } else {
        badge.textContent = "";
      }
    }
  }

  // ── Init ──
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", renderWidget);
  } else {
    renderWidget();
  }
})();
