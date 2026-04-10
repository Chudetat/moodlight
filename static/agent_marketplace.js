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
      @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&display=swap');

      #ml-marketplace * { box-sizing: border-box; margin: 0; padding: 0; }
      #ml-marketplace {
        font-family: 'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif;
        max-width: 720px;
        margin: 0 auto;
        color: #2D2D2D;
        padding: 12px 20px;
      }
      .ml-agents-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 12px;
        margin-bottom: 28px;
      }
      @media (max-width: 640px) {
        .ml-agents-grid { grid-template-columns: 1fr; }
        #ml-marketplace { padding: 12px; }
      }
      .ml-agent-card {
        border: 1px solid rgba(0, 0, 0, 0.12);
        border-radius: 12px;
        padding: 20px;
        cursor: pointer;
        transition: all 0.2s ease;
        background: rgba(0, 0, 0, 0.04);
        position: relative;
      }
      .ml-agent-card:hover {
        background: rgba(0, 0, 0, 0.08);
        border-color: rgba(0, 0, 0, 0.18);
      }
      .ml-agent-card.ml-selected {
        border-color: rgba(107, 70, 193, 0.5);
        box-shadow: 0 0 0 1px rgba(107, 70, 193, 0.3);
        background: rgba(107, 70, 193, 0.04);
      }
      .ml-agent-card .ml-icon {
        font-size: 22px;
        margin-bottom: 8px;
        display: block;
      }
      .ml-agent-card h3 {
        font-size: 16px;
        font-weight: 600;
        margin-bottom: 6px;
        color: #2D2D2D;
      }
      .ml-agent-card p {
        font-size: 13px;
        line-height: 1.5;
        color: rgba(45, 45, 45, 0.65);
      }
      .ml-premium-badge {
        position: absolute;
        top: 12px;
        right: 12px;
        background: linear-gradient(135deg, #6B46C1, #1976D2);
        color: #fff;
        font-size: 10px;
        font-weight: 600;
        padding: 3px 8px;
        border-radius: 10px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
      .ml-form-section {
        display: none;
        background: rgba(0, 0, 0, 0.03);
        border: 1px solid rgba(0, 0, 0, 0.08);
        border-radius: 12px;
        padding: 28px;
        margin-bottom: 24px;
      }
      .ml-form-section.ml-visible { display: block; }
      .ml-form-section h3 {
        font-size: 18px;
        font-weight: 600;
        margin-bottom: 4px;
        color: #2D2D2D;
      }
      .ml-form-section .ml-subtitle {
        font-size: 13px;
        color: rgba(45, 45, 45, 0.5);
        margin-bottom: 24px;
      }
      .ml-field {
        margin-bottom: 14px;
      }
      .ml-field label {
        display: block;
        font-size: 13px;
        font-weight: 500;
        color: rgba(45, 45, 45, 0.7);
        margin-bottom: 4px;
      }
      .ml-field label .ml-optional {
        font-weight: 400;
        color: rgba(45, 45, 45, 0.4);
      }
      .ml-field input {
        width: 100%;
        padding: 12px 16px;
        font-size: 15px;
        border: 1px solid rgba(0, 0, 0, 0.12);
        border-radius: 10px;
        background: rgba(0, 0, 0, 0.04);
        color: #2D2D2D;
        outline: none;
        transition: border-color 0.2s, box-shadow 0.2s;
        font-family: 'Space Grotesk', sans-serif;
      }
      .ml-field input:focus {
        border-color: rgba(107, 70, 193, 0.5);
        box-shadow: 0 2px 12px rgba(107, 70, 193, 0.1);
      }
      .ml-field input::placeholder {
        color: rgba(45, 45, 45, 0.35);
      }
      .ml-submit-btn {
        width: 100%;
        padding: 14px;
        font-size: 15px;
        font-weight: 600;
        color: #fff;
        border: none;
        border-radius: 28px;
        cursor: pointer;
        margin-top: 8px;
        transition: opacity 0.2s, transform 0.2s;
        font-family: 'Space Grotesk', sans-serif;
        background: linear-gradient(135deg, #6B46C1, #1976D2);
      }
      .ml-submit-btn:hover { opacity: 0.9; transform: scale(1.01); }
      .ml-submit-btn:disabled {
        opacity: 0.4;
        cursor: not-allowed;
        transform: none;
      }
      .ml-status {
        text-align: center;
        padding: 14px;
        border-radius: 10px;
        margin-top: 16px;
        font-size: 14px;
        display: none;
      }
      .ml-status.ml-success {
        display: block;
        background: rgba(46, 125, 50, 0.06);
        color: #2E7D32;
        border: 1px solid rgba(46, 125, 50, 0.15);
      }
      .ml-status.ml-error {
        display: block;
        background: rgba(198, 40, 40, 0.06);
        color: #c62828;
        border: 1px solid rgba(198, 40, 40, 0.15);
      }
      .ml-status.ml-loading {
        display: block;
        background: rgba(107, 70, 193, 0.06);
        color: #6B46C1;
        border: 1px solid rgba(107, 70, 193, 0.15);
      }
      .ml-loading-steps {
        text-align: center;
        padding: 32px 16px;
        display: none;
      }
      .ml-loading-steps.ml-visible { display: block; }
      .ml-loading-steps .ml-spinner {
        width: 36px;
        height: 36px;
        border: 3px solid rgba(0, 0, 0, 0.08);
        border-top-color: #6B46C1;
        border-radius: 50%;
        animation: ml-spin 0.8s linear infinite;
        margin: 0 auto 20px;
      }
      @keyframes ml-spin {
        to { transform: rotate(360deg); }
      }
      .ml-loading-steps .ml-step {
        font-size: 14px;
        color: rgba(45, 45, 45, 0.6);
        transition: opacity 0.4s;
      }
      .ml-preview-section {
        display: none;
        margin-top: 24px;
      }
      .ml-preview-section.ml-visible { display: block; }
      .ml-preview-wrap {
        position: relative;
        background: rgba(0, 0, 0, 0.03);
        border: 1px solid rgba(0, 0, 0, 0.08);
        border-radius: 12px;
        padding: 20px 24px;
        overflow: hidden;
      }
      .ml-preview-text {
        font-size: 14px;
        line-height: 1.7;
        color: #3D3D3D;
        white-space: pre-wrap;
        word-wrap: break-word;
      }
      .ml-preview-fade {
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        height: 120px;
        background: linear-gradient(to bottom, rgba(245,245,245,0) 0%, rgba(245,245,245,1) 80%);
        pointer-events: none;
      }
      .ml-preview-cta {
        text-align: center;
        margin-top: 16px;
        padding: 14px;
        background: rgba(107, 70, 193, 0.05);
        border: 1px solid rgba(107, 70, 193, 0.12);
        border-radius: 10px;
      }
      .ml-preview-cta .ml-cta-main {
        font-size: 15px;
        font-weight: 600;
        color: #6B46C1;
        margin-bottom: 4px;
      }
      .ml-preview-cta .ml-cta-sub {
        font-size: 13px;
        color: rgba(45, 45, 45, 0.5);
      }
      .ml-powered-by {
        text-align: center;
        font-size: 11px;
        color: rgba(45, 45, 45, 0.35);
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
      { name: "product", label: "Product / Service", placeholder: "e.g. premium running shoe, fintech app, whiskey brand", required: true },
      { name: "audience", label: "Target Audience", placeholder: "e.g. women 25-40, urban professionals" },
      { name: "markets", label: "Markets / Geography", placeholder: "e.g. US, UK, Canada" },
      { name: "challenge", label: "Key Challenge", placeholder: "e.g. competing against On and Hoka, launching into a saturated market" },
      { name: "timeline", label: "Timeline / Budget", placeholder: "e.g. Q2 2026, $2M digital" },
      { name: "email", label: "Your Email", placeholder: "We'll send your full brief here", required: true },
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

    const statusEl = document.createElement("div");
    statusEl.className = "ml-status";

    // Loading steps animation
    const loadingSection = document.createElement("div");
    loadingSection.className = "ml-loading-steps";

    const loadingSteps = [
      "Scanning 70,000+ cultural signals...",
      "Reading the market mood...",
      "Mapping cultural patterns...",
      "Building your brief...",
    ];

    // Preview section
    const previewSection = document.createElement("div");
    previewSection.className = "ml-preview-section";

    submitBtn.addEventListener("click", async () => {
      const email = (inputs.email.value || "").trim();
      const product = (inputs.product.value || "").trim();

      if (!product) {
        statusEl.className = "ml-status ml-error";
        statusEl.textContent = "Please describe your product or service.";
        return;
      }
      if (!email || !email.includes("@")) {
        statusEl.className = "ml-status ml-error";
        statusEl.textContent = "Please enter a valid email address.";
        return;
      }
      if (!selectedAgent) {
        statusEl.className = "ml-status ml-error";
        statusEl.textContent = "Please select an agent above.";
        return;
      }

      // Hide form, show loading animation
      submitBtn.disabled = true;
      statusEl.className = "ml-status";
      statusEl.style.display = "none";
      previewSection.className = "ml-preview-section";

      loadingSection.innerHTML = '<div class="ml-spinner"></div><div class="ml-step"></div>';
      loadingSection.classList.add("ml-visible");

      const stepEl = loadingSection.querySelector(".ml-step");
      let stepIdx = 0;
      stepEl.textContent = loadingSteps[0];
      const stepInterval = setInterval(() => {
        stepIdx++;
        if (stepIdx < loadingSteps.length) {
          stepEl.textContent = loadingSteps[stepIdx];
        }
      }, 8000);

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

        clearInterval(stepInterval);
        loadingSection.classList.remove("ml-visible");

        const data = await res.json();

        if (res.ok && data.preview) {
          // Show preview with blur
          previewSection.innerHTML = `
            <div class="ml-preview-wrap">
              <div class="ml-preview-text">${data.preview.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}</div>
              <div class="ml-preview-fade"></div>
            </div>
            <div class="ml-preview-cta">
              <div class="ml-cta-main">Full brief sent to ${email}</div>
              <div class="ml-cta-sub">Check your inbox — the complete analysis is waiting for you.</div>
            </div>
          `;
          previewSection.classList.add("ml-visible");
          previewSection.scrollIntoView({ behavior: "smooth", block: "start" });
        } else if (res.ok) {
          statusEl.className = "ml-status ml-success";
          statusEl.textContent = data.message || "Your brief has been sent to your email.";
        } else {
          statusEl.className = "ml-status ml-error";
          statusEl.textContent = data.detail || "Something went wrong. Please try again.";
          submitBtn.disabled = false;
        }
      } catch (err) {
        clearInterval(stepInterval);
        loadingSection.classList.remove("ml-visible");
        statusEl.className = "ml-status ml-error";
        statusEl.textContent = "Network error. Please try again.";
        submitBtn.disabled = false;
      }
    });

    formSection.appendChild(formTitle);
    formSection.appendChild(subtitle);
    formSection.appendChild(fieldsContainer);
    formSection.appendChild(submitBtn);
    formSection.appendChild(statusEl);
    formSection.appendChild(loadingSection);
    formSection.appendChild(previewSection);

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
