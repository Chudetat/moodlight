/**
 * Ask Moodlight — Embeddable Chat Widget
 * Drop this script into any page to add the Ask Moodlight demo.
 *
 * Usage (Squarespace):
 *   <script src="https://your-api-domain.up.railway.app/static/ask_moodlight_widget.js"></script>
 *
 * Or inline embed (no floating button):
 *   <div id="ask-moodlight-embed"></div>
 *   <script src="https://your-api-domain.up.railway.app/static/ask_moodlight_widget.js"
 *           data-mode="inline" data-target="ask-moodlight-embed"></script>
 */

(function () {
  "use strict";

  // Auto-detect API base from script src
  const scriptTag = document.currentScript;
  const scriptSrc = scriptTag ? scriptTag.src : "";
  const API_BASE = scriptSrc
    ? scriptSrc.replace(/\/static\/ask_moodlight_widget\.js.*$/, "")
    : "https://ask-moodlight.up.railway.app";
  const MODE = scriptTag?.getAttribute("data-mode") || "floating";
  const TARGET = scriptTag?.getAttribute("data-target") || null;

  // State
  let conversation = [];
  let isOpen = false;
  let queriesRemaining = 3;

  // ── Styles ──
  const STYLES = `
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
    #ml-widget-btn svg {
      width: 28px;
      height: 28px;
      fill: white;
    }

    #ml-widget-panel {
      position: fixed;
      bottom: 96px;
      right: 24px;
      width: 380px;
      max-height: 520px;
      background: #0E1117;
      border: 1px solid rgba(107, 70, 193, 0.3);
      border-radius: 16px;
      box-shadow: 0 8px 40px rgba(0, 0, 0, 0.5);
      z-index: 10001;
      display: none;
      flex-direction: column;
      overflow: hidden;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    #ml-widget-panel.open { display: flex; }

    #ml-widget-panel.inline-mode {
      position: relative;
      bottom: auto;
      right: auto;
      width: 100%;
      max-width: 600px;
      max-height: 600px;
      margin: 0 auto;
      display: flex;
      border-radius: 12px;
    }

    .ml-header {
      padding: 16px 20px;
      background: linear-gradient(135deg, rgba(107, 70, 193, 0.15), rgba(25, 118, 210, 0.1));
      border-bottom: 1px solid rgba(107, 70, 193, 0.2);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .ml-header-title {
      color: #FAFAFA;
      font-size: 15px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .ml-header-title span {
      font-size: 18px;
    }
    .ml-header-badge {
      font-size: 11px;
      color: rgba(250, 250, 250, 0.5);
      background: rgba(107, 70, 193, 0.2);
      padding: 2px 8px;
      border-radius: 10px;
    }
    .ml-close-btn {
      background: none;
      border: none;
      color: rgba(250, 250, 250, 0.5);
      cursor: pointer;
      font-size: 20px;
      padding: 0;
      line-height: 1;
    }
    .ml-close-btn:hover { color: #FAFAFA; }

    .ml-messages {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      min-height: 200px;
    }
    .ml-messages::-webkit-scrollbar { width: 4px; }
    .ml-messages::-webkit-scrollbar-track { background: transparent; }
    .ml-messages::-webkit-scrollbar-thumb { background: rgba(107, 70, 193, 0.3); border-radius: 2px; }

    .ml-msg {
      max-width: 85%;
      padding: 10px 14px;
      border-radius: 12px;
      font-size: 13px;
      line-height: 1.5;
      word-wrap: break-word;
    }
    .ml-msg-user {
      align-self: flex-end;
      background: linear-gradient(135deg, #6B46C1, #1976D2);
      color: white;
      border-bottom-right-radius: 4px;
    }
    .ml-msg-assistant {
      align-self: flex-start;
      background: rgba(255, 255, 255, 0.08);
      color: #E0E0E0;
      border-bottom-left-radius: 4px;
    }
    .ml-msg-assistant strong { color: #FAFAFA; }

    .ml-welcome {
      color: rgba(250, 250, 250, 0.6);
      font-size: 13px;
      text-align: center;
      padding: 20px 16px;
    }
    .ml-welcome-prompt {
      display: inline-block;
      background: rgba(107, 70, 193, 0.15);
      border: 1px solid rgba(107, 70, 193, 0.25);
      border-radius: 8px;
      padding: 6px 12px;
      margin: 4px;
      font-size: 12px;
      color: rgba(250, 250, 250, 0.7);
      cursor: pointer;
      transition: background 0.2s;
    }
    .ml-welcome-prompt:hover {
      background: rgba(107, 70, 193, 0.3);
      color: #FAFAFA;
    }

    .ml-input-area {
      padding: 12px 16px;
      border-top: 1px solid rgba(107, 70, 193, 0.15);
      display: flex;
      gap: 8px;
      align-items: center;
    }
    .ml-input {
      flex: 1;
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid rgba(107, 70, 193, 0.2);
      border-radius: 8px;
      padding: 10px 14px;
      color: #FAFAFA;
      font-size: 13px;
      outline: none;
      transition: border-color 0.2s;
    }
    .ml-input::placeholder { color: rgba(250, 250, 250, 0.35); }
    .ml-input:focus { border-color: rgba(107, 70, 193, 0.5); }
    .ml-input:disabled { opacity: 0.5; }

    .ml-send-btn {
      background: linear-gradient(135deg, #6B46C1, #1976D2);
      border: none;
      border-radius: 8px;
      padding: 10px 14px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: opacity 0.2s;
    }
    .ml-send-btn:hover { opacity: 0.85; }
    .ml-send-btn:disabled { opacity: 0.4; cursor: not-allowed; }
    .ml-send-btn svg { width: 16px; height: 16px; fill: white; }

    .ml-footer {
      padding: 8px 16px;
      text-align: center;
      font-size: 11px;
      color: rgba(250, 250, 250, 0.3);
      border-top: 1px solid rgba(107, 70, 193, 0.1);
    }
    .ml-footer a {
      color: rgba(107, 70, 193, 0.6);
      text-decoration: none;
    }
    .ml-footer a:hover { color: #6B46C1; }

    .ml-typing {
      display: flex;
      gap: 4px;
      padding: 10px 14px;
      align-self: flex-start;
    }
    .ml-typing-dot {
      width: 6px;
      height: 6px;
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

    .ml-limit-msg {
      color: rgba(250, 250, 250, 0.5);
      font-size: 11px;
      text-align: center;
      padding: 4px;
    }
  `;

  // ── Inject styles ──
  const styleEl = document.createElement("style");
  styleEl.textContent = STYLES;
  document.head.appendChild(styleEl);

  // ── Render widget ──
  function renderWidget() {
    if (MODE === "inline" && TARGET) {
      renderInline();
    } else {
      renderFloating();
    }
  }

  function renderFloating() {
    // Floating button
    const btn = document.createElement("button");
    btn.id = "ml-widget-btn";
    btn.innerHTML = `<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.17L4 17.17V4h16v12z"/><path d="M7 9h2v2H7zm4 0h2v2h-2zm4 0h2v2h-2z"/></svg>`;
    btn.title = "Ask Moodlight";
    btn.onclick = togglePanel;
    document.body.appendChild(btn);

    // Panel
    const panel = createPanel(false);
    document.body.appendChild(panel);
  }

  function renderInline() {
    const target = document.getElementById(TARGET);
    if (!target) return;
    const panel = createPanel(true);
    panel.classList.add("inline-mode");
    target.appendChild(panel);
  }

  function createPanel(inlineMode) {
    const panel = document.createElement("div");
    panel.id = "ml-widget-panel";
    if (inlineMode) panel.classList.add("open");

    const suggestedPrompts = [
      "What brands are gaining momentum?",
      "Where's the white space right now?",
      "What should Nike be watching?",
    ];

    panel.innerHTML = `
      <div class="ml-header">
        <div class="ml-header-title">
          <span>💬</span> Ask Moodlight
        </div>
        <div style="display: flex; align-items: center; gap: 8px;">
          <span class="ml-header-badge" id="ml-queries-badge">${queriesRemaining} questions left</span>
          ${inlineMode ? "" : '<button class="ml-close-btn" onclick="document.getElementById(\'ml-widget-panel\').classList.remove(\'open\')">&times;</button>'}
        </div>
      </div>
      <div class="ml-messages" id="ml-messages">
        <div class="ml-welcome">
          Real-time cultural intelligence, powered by AI.<br><br>
          Try asking:
          <div style="margin-top: 8px;">
            ${suggestedPrompts.map((p) => `<div class="ml-welcome-prompt" onclick="window._mlAsk('${p}')">${p}</div>`).join("")}
          </div>
        </div>
      </div>
      <div class="ml-input-area">
        <input class="ml-input" id="ml-input" type="text"
               placeholder="Ask about brands, trends, or strategy..."
               maxlength="500"
               onkeydown="if(event.key==='Enter')window._mlSend()">
        <button class="ml-send-btn" id="ml-send-btn" onclick="window._mlSend()">
          <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
        </button>
      </div>
      <div class="ml-footer">
        Powered by <a href="https://moodlightintel.com" target="_blank">Moodlight Intelligence</a>
      </div>
    `;

    return panel;
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
      addMessage(
        messages,
        "assistant",
        "You've used your 3 free questions for today. Sign up at [moodlightintel.com](https://moodlightintel.com) for unlimited access to Ask Moodlight."
      );
      return;
    }

    // Clear welcome message
    const welcome = messages.querySelector(".ml-welcome");
    if (welcome) welcome.remove();

    // Add user message
    addMessage(messages, "user", question);
    input.value = "";
    input.disabled = true;
    sendBtn.disabled = true;

    // Add typing indicator
    const typing = document.createElement("div");
    typing.className = "ml-typing";
    typing.innerHTML = '<div class="ml-typing-dot"></div><div class="ml-typing-dot"></div><div class="ml-typing-dot"></div>';
    messages.appendChild(typing);
    messages.scrollTop = messages.scrollHeight;

    try {
      const res = await fetch(API_BASE + "/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: question,
          conversation: conversation,
        }),
      });

      typing.remove();

      if (res.status === 429) {
        queriesRemaining = 0;
        updateBadge();
        addMessage(
          messages,
          "assistant",
          "You've used your 3 free questions for today. Sign up at [moodlightintel.com](https://moodlightintel.com) for unlimited access."
        );
        return;
      }

      if (!res.ok) {
        addMessage(messages, "assistant", "Something went wrong. Please try again.");
        return;
      }

      const data = await res.json();
      conversation.push({ role: "user", content: question });
      conversation.push({ role: "assistant", content: data.answer });
      queriesRemaining = data.queries_remaining;
      updateBadge();

      addMessage(messages, "assistant", data.answer);
    } catch (err) {
      typing.remove();
      addMessage(messages, "assistant", "Connection error. Please try again.");
    } finally {
      input.disabled = false;
      sendBtn.disabled = false;
      input.focus();
    }
  };

  function addMessage(container, role, text) {
    const el = document.createElement("div");
    el.className = `ml-msg ml-msg-${role}`;
    // Basic markdown: bold, line breaks
    el.innerHTML = text
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/\n/g, "<br>");
    container.appendChild(el);
    container.scrollTop = container.scrollHeight;
  }

  function updateBadge() {
    const badge = document.getElementById("ml-queries-badge");
    if (badge) {
      badge.textContent =
        queriesRemaining > 0
          ? `${queriesRemaining} question${queriesRemaining !== 1 ? "s" : ""} left`
          : "Sign up for more";
    }
  }

  // ── Init ──
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", renderWidget);
  } else {
    renderWidget();
  }
})();
