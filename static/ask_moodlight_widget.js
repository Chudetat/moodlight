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
  let queriesRemaining = 3;
  let hasSearched = false;

  // ── Styles ──
  const STYLES = `
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

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
    #ml-widget-btn svg { width: 28px; height: 28px; fill: white; }

    /* ── Floating panel ── */
    #ml-widget-panel.floating-mode {
      position: fixed;
      bottom: 96px;
      right: 24px;
      width: 400px;
      max-height: 560px;
      background: #0E1117;
      border: 1px solid rgba(107, 70, 193, 0.25);
      border-radius: 16px;
      box-shadow: 0 8px 40px rgba(0, 0, 0, 0.5);
      z-index: 10001;
      display: none;
      flex-direction: column;
      overflow: hidden;
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
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
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      padding: 12px 20px;
    }

    /* ── Logo area ── */
    .ml-logo {
      text-align: center;
      padding: 6px 0 18px 0;
    }
    .ml-logo-text {
      font-size: 56px;
      font-weight: 500;
      color: #FAFAFA;
      font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
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
      color: rgba(250, 250, 250, 0.4);
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
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid rgba(107, 70, 193, 0.25);
      border-radius: 28px;
      padding: 16px 56px 16px 24px;
      color: #FAFAFA;
      font-size: 16px;
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      outline: none;
      transition: border-color 0.3s, box-shadow 0.3s, background 0.3s;
      box-sizing: border-box;
    }
    .ml-search-bar::placeholder {
      color: rgba(250, 250, 250, 0.3);
      font-weight: 300;
    }
    .ml-search-bar:focus {
      border-color: rgba(107, 70, 193, 0.5);
      box-shadow: 0 4px 24px rgba(107, 70, 193, 0.15);
      background: rgba(255, 255, 255, 0.08);
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
      flex-wrap: wrap;
      justify-content: center;
      gap: 8px;
      margin-top: 14px;
      max-width: 580px;
    }
    .ml-prompt-chip {
      background: rgba(107, 70, 193, 0.1);
      border: 1px solid rgba(107, 70, 193, 0.2);
      border-radius: 20px;
      padding: 8px 16px;
      font-size: 13px;
      color: rgba(250, 250, 250, 0.6);
      cursor: pointer;
      transition: all 0.2s;
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .ml-prompt-chip:hover {
      background: rgba(107, 70, 193, 0.2);
      border-color: rgba(107, 70, 193, 0.4);
      color: #FAFAFA;
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
    .ml-results::-webkit-scrollbar-thumb { background: rgba(107, 70, 193, 0.3); border-radius: 2px; }

    .ml-result-user {
      font-size: 14px;
      color: rgba(250, 250, 250, 0.5);
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
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid rgba(107, 70, 193, 0.12);
      border-radius: 12px;
      padding: 16px 20px;
      color: #E0E0E0;
      font-size: 14px;
      line-height: 1.6;
      word-wrap: break-word;
    }
    .ml-result-card strong { color: #FAFAFA; }
    .ml-result-card p { margin: 8px 0; }

    /* ── Typing indicator ── */
    .ml-typing-bar {
      display: flex;
      gap: 5px;
      padding: 20px 24px;
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid rgba(107, 70, 193, 0.12);
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
      color: rgba(250, 250, 250, 0.35);
      text-align: center;
      margin-top: 12px;
    }

    /* ── Footer ── */
    .ml-footer-inline {
      margin-top: 16px;
      text-align: center;
      font-size: 11px;
      color: rgba(250, 250, 250, 0.25);
    }
    .ml-footer-inline a {
      color: rgba(107, 70, 193, 0.5);
      text-decoration: none;
    }
    .ml-footer-inline a:hover { color: #6B46C1; }

    /* ── Floating panel header ── */
    .ml-float-header {
      padding: 14px 20px;
      background: linear-gradient(135deg, rgba(107, 70, 193, 0.12), rgba(25, 118, 210, 0.08));
      border-bottom: 1px solid rgba(107, 70, 193, 0.15);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .ml-float-header-title {
      font-size: 14px;
      font-weight: 600;
      color: #FAFAFA;
    }
    .ml-float-close {
      background: none;
      border: none;
      color: rgba(250, 250, 250, 0.4);
      cursor: pointer;
      font-size: 20px;
      padding: 0;
      line-height: 1;
    }
    .ml-float-close:hover { color: #FAFAFA; }

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
    btn.innerHTML = '<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.17L4 17.17V4h16v12z"/><path d="M7 9h2v2H7zm4 0h2v2h-2zm4 0h2v2h-2z"/></svg>';
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
          <div class="ml-logo-text" style="font-size: 28px;">Moodlight</div>
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
        <div class="ml-queries-badge" id="ml-queries-badge">${queriesRemaining} free questions remaining</div>
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

    const suggestedPrompts = [
      "What should Nike be watching right now?",
      "Which cultural signals are brands missing?",
      "Give me a competitive read on Oatly",
    ];

    panel.innerHTML = `
      <div class="ml-logo">
        <div class="ml-logo-text"><span class="ml-logo-icon">💬</span> Ask Moodlight</div>
        <div class="ml-logo-sub">Real-time intelligence for brands that move at the speed of culture</div>
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
        ${suggestedPrompts.map((p) => `<div class="ml-prompt-chip" onclick="window._mlAsk('${p}')">${p}</div>`).join("")}
      </div>

      <div class="ml-results" id="ml-messages"></div>

      <div class="ml-queries-badge" id="ml-queries-badge">${queriesRemaining} free questions remaining</div>

      <div class="ml-footer-inline">
        <a href="https://moodlightintel.com" target="_blank">moodlightintel.com</a>
      </div>
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
  window._mlAsk = function (prompt) {
    const input = document.getElementById("ml-input");
    if (input) {
      input.value = prompt;
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
    if (queriesRemaining <= 0) {
      addResult(messages, "assistant", "You've used your 3 free questions for today. Sign up for unlimited access to Ask Moodlight and the full intelligence platform.");
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
        body: JSON.stringify({ question, conversation }),
      });

      typing.remove();

      if (res.status === 429) {
        queriesRemaining = 0;
        updateBadge();
        addResult(messages, "assistant", "You've used your 3 free questions for today. Sign up for unlimited access to the full intelligence platform.");
        return;
      }

      if (!res.ok) {
        addResult(messages, "assistant", "Something went wrong. Please try again.");
        return;
      }

      const data = await res.json();
      conversation.push({ role: "user", content: question });
      conversation.push({ role: "assistant", content: data.answer });
      queriesRemaining = data.queries_remaining;
      updateBadge();

      addResult(messages, "assistant", data.answer);
    } catch (err) {
      typing.remove();
      addResult(messages, "assistant", "Connection error. Please try again.");
    } finally {
      input.disabled = false;
      sendBtn.disabled = false;
      input.focus();
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
      badge.textContent =
        queriesRemaining > 0
          ? `${queriesRemaining} free question${queriesRemaining !== 1 ? "s" : ""} remaining`
          : "Sign up for unlimited access";
    }
  }

  // ── Init ──
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", renderWidget);
  } else {
    renderWidget();
  }
})();
