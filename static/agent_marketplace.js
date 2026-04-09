/**
 * Moodlight Agent Marketplace — Embeddable widget for Squarespace.
 *
 * Usage:
 *   <div id="moodlight-marketplace"></div>
 *   <script src="https://moodlight-api-production.up.railway.app/static/agent_marketplace.js"></script>
 */

(function () {
  "use strict";

  const scriptTag = document.currentScript;
  const scriptSrc = scriptTag ? scriptTag.src : "";
  const API_BASE = scriptSrc
    ? scriptSrc.replace(/\/static\/agent_marketplace\.js.*$/, "")
    : "https://moodlight-api-production.up.railway.app";

  const AGENTS = [
    {
      id: "cco",
      title: "The Chief Creative Officer",
      desc: "Builds campaign concepts from live cultural signals. The brief it writes on Tuesday is different from the one it writes on Thursday. Because the culture moved.",
      icon: "\u2728",
      color: "#7B1FA2",
    },
    {
      id: "cso",
      title: "The Chief Strategy Officer",
      desc: "Reads the market, the mood, and the momentum. Picks a position. Defends it with data. Doesn't hedge.",
      icon: "\u265F",
      color: "#1565C0",
    },
    {
      id: "comms-planner",
      title: "The Comms Planner",
      desc: "Tells you where to show up, when to deploy, and what to skip. Every recommendation backed by where attention actually is.",
      icon: "\uD83D\uDCE1",
      color: "#2E7D32",
    },
    {
      id: "full-deploy",
      title: "Full Deploy",
      desc: "All three working as one team. One input, one complete battle plan: strategy, creative, and distribution that don't contradict each other.",
      icon: "\uD83D\uDE80",
      color: "#D84315",
      premium: true,
    },
  ];

  function injectStyles() {
    const css = `
      #ml-marketplace * { box-sizing: border-box; margin: 0; padding: 0; }
      #ml-marketplace {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        max-width: 900px;
        margin: 0 auto;
        color: #1a1a1a;
      }
      .ml-agents-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 20px;
        margin-bottom: 32px;
      }
      @media (max-width: 640px) {
        .ml-agents-grid { grid-template-columns: 1fr; }
      }
      .ml-agent-card {
        border: 2px solid #e0e0e0;
        border-radius: 12px;
        padding: 24px;
        cursor: pointer;
        transition: all 0.2s ease;
        background: #fff;
        position: relative;
      }
      .ml-agent-card:hover {
        border-color: #333;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
      }
      .ml-agent-card.ml-selected {
        border-color: var(--agent-color, #333);
        box-shadow: 0 0 0 1px var(--agent-color, #333);
      }
      .ml-agent-card .ml-icon {
        font-size: 28px;
        margin-bottom: 12px;
        display: block;
      }
      .ml-agent-card h3 {
        font-size: 18px;
        font-weight: 700;
        margin-bottom: 8px;
        color: #1a1a1a;
      }
      .ml-agent-card p {
        font-size: 14px;
        line-height: 1.5;
        color: #555;
      }
      .ml-premium-badge {
        position: absolute;
        top: 12px;
        right: 12px;
        background: #D84315;
        color: #fff;
        font-size: 11px;
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 4px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
      .ml-form-section {
        display: none;
        background: #fafafa;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 32px;
        margin-bottom: 24px;
      }
      .ml-form-section.ml-visible { display: block; }
      .ml-form-section h3 {
        font-size: 20px;
        font-weight: 700;
        margin-bottom: 4px;
      }
      .ml-form-section .ml-subtitle {
        font-size: 14px;
        color: #777;
        margin-bottom: 24px;
      }
      .ml-field {
        margin-bottom: 16px;
      }
      .ml-field label {
        display: block;
        font-size: 13px;
        font-weight: 600;
        color: #333;
        margin-bottom: 4px;
      }
      .ml-field label .ml-optional {
        font-weight: 400;
        color: #999;
      }
      .ml-field input {
        width: 100%;
        padding: 10px 12px;
        font-size: 15px;
        border: 1px solid #d0d0d0;
        border-radius: 8px;
        background: #fff;
        color: #1a1a1a;
        outline: none;
        transition: border-color 0.15s;
        font-family: inherit;
      }
      .ml-field input:focus {
        border-color: #333;
      }
      .ml-field input::placeholder {
        color: #aaa;
      }
      .ml-submit-btn {
        width: 100%;
        padding: 14px;
        font-size: 16px;
        font-weight: 700;
        color: #fff;
        border: none;
        border-radius: 8px;
        cursor: pointer;
        margin-top: 8px;
        transition: opacity 0.15s;
        font-family: inherit;
      }
      .ml-submit-btn:hover { opacity: 0.9; }
      .ml-submit-btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
      .ml-status {
        text-align: center;
        padding: 16px;
        border-radius: 8px;
        margin-top: 16px;
        font-size: 15px;
        display: none;
      }
      .ml-status.ml-success {
        display: block;
        background: #e8f5e9;
        color: #2E7D32;
        border: 1px solid #c8e6c9;
      }
      .ml-status.ml-error {
        display: block;
        background: #fbe9e7;
        color: #c62828;
        border: 1px solid #ffccbc;
      }
      .ml-status.ml-loading {
        display: block;
        background: #f3e5f5;
        color: #7B1FA2;
        border: 1px solid #e1bee7;
      }
      .ml-powered-by {
        text-align: center;
        font-size: 12px;
        color: #999;
        margin-top: 24px;
      }
    `;
    const style = document.createElement("style");
    style.textContent = css;
    document.head.appendChild(style);
  }

  function buildUI(container) {
    let selectedAgent = null;

    // Agent cards
    const grid = document.createElement("div");
    grid.className = "ml-agents-grid";

    AGENTS.forEach((agent) => {
      const card = document.createElement("div");
      card.className = "ml-agent-card";
      card.style.setProperty("--agent-color", agent.color);
      card.innerHTML = `
        <span class="ml-icon">${agent.icon}</span>
        ${agent.premium ? '<span class="ml-premium-badge">All Three</span>' : ""}
        <h3>${agent.title}</h3>
        <p>${agent.desc}</p>
      `;
      card.addEventListener("click", () => {
        grid.querySelectorAll(".ml-agent-card").forEach((c) => c.classList.remove("ml-selected"));
        card.classList.add("ml-selected");
        selectedAgent = agent.id;
        formSection.classList.add("ml-visible");
        formTitle.textContent = agent.title;
        submitBtn.style.background = agent.color;
        submitBtn.textContent = `Generate ${agent.title} Brief`;
        statusEl.className = "ml-status";
        statusEl.style.display = "none";
      });
      grid.appendChild(card);
    });

    // Form section
    const formSection = document.createElement("div");
    formSection.className = "ml-form-section";

    const formTitle = document.createElement("h3");
    formTitle.textContent = "";

    const subtitle = document.createElement("div");
    subtitle.className = "ml-subtitle";
    subtitle.textContent = "The more detail you provide, the better your brief.";

    const fields = [
      { name: "email", label: "Email Address", placeholder: "Where we'll send your brief", required: true },
      { name: "product", label: "Product / Service", placeholder: "e.g. premium running shoe, fintech app, whiskey brand", required: true },
      { name: "audience", label: "Target Audience", placeholder: "e.g. women 25-40, urban professionals" },
      { name: "markets", label: "Markets / Geography", placeholder: "e.g. US, UK, Canada" },
      { name: "challenge", label: "Key Challenge", placeholder: "e.g. competing against On and Hoka, launching into a saturated market" },
      { name: "timeline", label: "Timeline / Budget", placeholder: "e.g. Q2 2026, $2M digital" },
    ];

    const inputs = {};
    const fieldsContainer = document.createElement("div");

    fields.forEach((f) => {
      const div = document.createElement("div");
      div.className = "ml-field";
      const optTag = f.required ? "" : ' <span class="ml-optional">(optional)</span>';
      div.innerHTML = `<label>${f.label}${optTag}</label>`;
      const input = document.createElement("input");
      input.type = f.name === "email" ? "email" : "text";
      input.placeholder = f.placeholder;
      input.name = f.name;
      inputs[f.name] = input;
      div.appendChild(input);
      fieldsContainer.appendChild(div);
    });

    const submitBtn = document.createElement("button");
    submitBtn.className = "ml-submit-btn";
    submitBtn.textContent = "Generate Brief";
    submitBtn.style.background = "#333";

    const statusEl = document.createElement("div");
    statusEl.className = "ml-status";

    submitBtn.addEventListener("click", async () => {
      const email = (inputs.email.value || "").trim();
      const product = (inputs.product.value || "").trim();

      if (!email || !email.includes("@")) {
        statusEl.className = "ml-status ml-error";
        statusEl.textContent = "Please enter a valid email address.";
        return;
      }
      if (!product) {
        statusEl.className = "ml-status ml-error";
        statusEl.textContent = "Please describe your product or service.";
        return;
      }
      if (!selectedAgent) {
        statusEl.className = "ml-status ml-error";
        statusEl.textContent = "Please select an agent above.";
        return;
      }

      submitBtn.disabled = true;
      statusEl.className = "ml-status ml-loading";
      statusEl.textContent = "Submitting your brief request...";

      try {
        const res = await fetch(API_BASE + "/api/marketplace/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            agent: selectedAgent,
            email: email,
            product: product,
            audience: inputs.audience.value || "",
            markets: inputs.markets.value || "",
            challenge: inputs.challenge.value || "",
            timeline: inputs.timeline.value || "",
          }),
        });

        const data = await res.json();

        if (res.ok) {
          statusEl.className = "ml-status ml-success";
          statusEl.textContent = data.message || "Your brief is being generated. Check your email.";
        } else {
          statusEl.className = "ml-status ml-error";
          statusEl.textContent = data.detail || "Something went wrong. Please try again.";
        }
      } catch (err) {
        statusEl.className = "ml-status ml-error";
        statusEl.textContent = "Network error. Please try again.";
      }

      submitBtn.disabled = false;
    });

    formSection.appendChild(formTitle);
    formSection.appendChild(subtitle);
    formSection.appendChild(fieldsContainer);
    formSection.appendChild(submitBtn);
    formSection.appendChild(statusEl);

    // Powered by
    const powered = document.createElement("div");
    powered.className = "ml-powered-by";
    powered.textContent = "Powered by Moodlight Real-Time Intelligence";

    container.appendChild(grid);
    container.appendChild(formSection);
    container.appendChild(powered);
  }

  function init() {
    const container = document.getElementById("moodlight-marketplace");
    if (!container) {
      console.error("Moodlight Marketplace: #moodlight-marketplace container not found");
      return;
    }

    container.id = "ml-marketplace";
    injectStyles();
    buildUI(container);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
