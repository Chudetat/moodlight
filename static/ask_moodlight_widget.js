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
      text-align: center;
      margin-top: 12px;
    }
    .ml-agent-cta-btn {
      display: inline-block;
      background: linear-gradient(135deg, #6B46C1, #1976D2);
      color: white;
      border: none;
      border-radius: 20px;
      padding: 10px 24px;
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
    // so visitors see different agents across the 16-agent marketplace
    const promptPools = [
      [
        "Build a prompt for the Chief Creative Officer agent around Nike",
        "Build a Crisis Advisor prompt for Boeing",
        "Build a Trend Forecaster brief for Rhode",
        "Build a Pitch Builder deck for a new business win",
        "Build a SEO Strategist brief for Patagonia",
        "Build a Cultural Strategist brief for Airbnb",
      ],
      [
        "What's the cultural read around Microsoft right now?",
        "What's shifting in Gen Z attention right now?",
        "Where is the conversation moving on AI and labor?",
        "What's the mood around luxury brands right now?",
      ],
      [
        "Run a Brand Audit on Netflix",
        "Run a Competitive Scout on Spotify",
        "Run an Audience Profiler on Peloton",
        "Run a Content Strategist on Glossier",
        "Run a Social Strategist on Duolingo",
      ],
    ];
    const suggestedPrompts = promptPools.map(
      (pool) => pool[Math.floor(Math.random() * pool.length)]
    );

    panel.innerHTML = `
      <div class="ml-logo">
        <div class="ml-logo-text"><span class="ml-logo-icon"><img src="${API_BASE}/static/logo_black.png" alt="Moodlight" style="width:48px;height:48px;vertical-align:middle"></span> Ask Moodlight</div>
      </div>

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
        body: JSON.stringify({ question, conversation, token: paidToken }),
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
      if (data.answer.includes("**Product/Service:**")) {
        showAgentCta(messages, data.answer);
      }
      showNewQuestionBtn(messages);
    } catch (err) {
      typing.remove();
      addResult(messages, "assistant", "Connection error. Please try again.");
    } finally {
      input.disabled = false;
      sendBtn.disabled = false;
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

  function showAgentCta(container, answer) {
    const existing = container.querySelector(".ml-agent-cta");
    if (existing) existing.remove();

    // Detect which agent was mentioned
    const agentMap = {
      "Chief Creative Officer": "cco",
      "CCO": "cco",
      "Cultural Strategist": "cso",
      "Comms Planner": "comms-planner",
      "Full Deploy": "full-deploy",
      "Brand Auditor": "brand-auditor",
      "Brief Critic": "brief-critic",
      "Trend Forecaster": "trend-forecaster",
      "Copywriter": "copywriter",
      "Crisis Advisor": "crisis-advisor",
      "Audience Profiler": "audience-profiler",
      "Competitive Scout": "competitive-scout",
      "Pitch Builder": "pitch-builder",
      "Content Strategist": "content-strategist",
      "Culture Translator": "culture-translator",
      "SEO Strategist": "seo-strategist",
      "Social Strategist": "social-strategist",
    };

    let detectedAgent = null;
    for (const [name, id] of Object.entries(agentMap)) {
      if (answer.includes(name)) { detectedAgent = id; break; }
    }

    const el = document.createElement("div");
    el.className = "ml-agent-cta";
    const btn = document.createElement("button");
    btn.className = "ml-agent-cta-btn";
    btn.textContent = "Run this in the Agent Marketplace \u2193";
    // Parse brief fields from the answer
    var parsedFields = {};
    var fieldPatterns = {
      product: /\*\*Product\/Service:\*\*\s*(.+)/i,
      audience: /\*\*Target Audience:\*\*\s*(.+)/i,
      markets: /\*\*Markets\/Geography:\*\*\s*(.+)/i,
      challenge: /\*\*Key Challenge:\*\*\s*(.+)/i,
      timeline: /\*\*Timeline\/Budget:\*\*\s*(.+)/i,
    };
    for (var key in fieldPatterns) {
      var m = answer.match(fieldPatterns[key]);
      if (m) parsedFields[key] = m[1].trim();
    }

    btn.onclick = function () {
      // Store parsed fields globally so the marketplace can fill them on any agent selection
      window._mlParsedBriefFields = parsedFields;

      var marketplace = document.getElementById("ml-marketplace") || document.getElementById("moodlight-marketplace");
      if (marketplace) {
        marketplace.scrollIntoView({ behavior: "smooth", block: "start" });
        // Auto-select the detected agent card
        if (detectedAgent) {
          setTimeout(function () {
            var cards = marketplace.querySelectorAll(".ml-agent-card");
            cards.forEach(function (card) {
              var title = card.querySelector("h3");
              if (title) {
                var match = Object.entries(agentMap).find(function (entry) { return entry[1] === detectedAgent; });
                if (match && title.textContent.includes(match[0])) {
                  card.click();
                }
              }
            });
          }, 500);
        }
      }
    };
    el.appendChild(btn);
    container.appendChild(el);
    container.scrollTop = container.scrollHeight;
  }

  window._mlClear = function () {
    const messages = document.getElementById("ml-messages");
    if (messages) messages.innerHTML = "";
    const input = document.getElementById("ml-input");
    if (input) {
      input.value = "";
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
