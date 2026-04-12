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
      title: "The Cultural Strategist",
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
    {
      id: "data-strategist",
      title: "The Data Strategist",
      desc: "Builds the KPI tree, kills the vanity metrics, and tells you which first-party data to activate. A measurement plan that actually ladders to revenue — not a dashboard graveyard.",
      icon: "\uD83D\uDCCA",
      color: "#37474F",
    },
    {
      id: "creative-technologist",
      title: "The Creative Technologist",
      desc: "Translates a concept into a stack, a prototype, and a build plan. Tells you what to build, what to buy, what will break, and when to walk away. No hype — just what ships.",
      icon: "\uD83D\uDEE0\uFE0F",
      color: "#5D4037",
    },
    {
      id: "brand-auditor",
      title: "The Brand Auditor",
      desc: "Type your brand. See where you stand culturally — what you own, what you're missing, and where the whitespace is. A full diagnostic in 60 seconds.",
      icon: "\uD83D\uDD0D",
      color: "#00838F",
    },
    {
      id: "brief-critic",
      title: "The Brief Critic",
      desc: "Paste your brief. Get it torn apart against live data. Finds what's stale, what's wrong, and what the data says you should be doing instead.",
      icon: "\u2702\uFE0F",
      color: "#AD1457",
    },
    {
      id: "trend-forecaster",
      title: "The Trend Forecaster",
      desc: "Not what's trending now — what's next. Reads velocity, scarcity, and signal clusters to predict cultural shifts before they have names.",
      icon: "\uD83D\uDD2E",
      color: "#E65100",
    },
    {
      id: "copywriter",
      title: "The Copywriter",
      desc: "Headlines, social posts, and ad copy tuned to the cultural moment. Every line is built on what's happening right now, not what was approved last month.",
      icon: "\u270D\uFE0F",
      color: "#283593",
    },
    {
      id: "crisis-advisor",
      title: "The Crisis Advisor",
      desc: "Your brand just got tagged in something. Here's what to say, what not to say, and how fast you need to move. Real-time crisis response, not a PR playbook.",
      icon: "\u26A1",
      color: "#B71C1C",
    },
    {
      id: "audience-profiler",
      title: "The Audience Profiler",
      desc: "Who's actually talking about your brand, what they care about, and where they're drifting. Psychographic intelligence from live signals, not stale persona decks.",
      icon: "\uD83C\uDFAF",
      color: "#4A148C",
    },
    {
      id: "competitive-scout",
      title: "The Competitive Scout",
      desc: "What cultural territory your competitors are claiming, where they're vulnerable, and what they're sleeping on. Head-to-head intelligence from live data.",
      icon: "\uD83D\uDD75\uFE0F",
      color: "#1B5E20",
    },
    {
      id: "partnership-scout",
      title: "The Partnership Scout",
      desc: "The opposite of the Competitive Scout. Finds unexpected brand, creator, and institution collabs — with the value exchange, the risk read, and how to actually make the ask.",
      icon: "\uD83E\uDD1D",
      color: "#6A1B9A",
    },
    {
      id: "pitch-builder",
      title: "The Pitch Builder",
      desc: "Turns any brief or strategy into a client-ready pitch narrative. The insight that wins the room, the setup that makes inaction feel dangerous.",
      icon: "\uD83C\uDFAC",
      color: "#F57F17",
    },
    {
      id: "content-strategist",
      title: "The Content Strategist",
      desc: "Content pillars, editorial rhythm, and platform angles built from what the culture is actually talking about. Not a calendar — a content ecosystem.",
      icon: "\uD83D\uDCDD",
      color: "#0277BD",
    },
    {
      id: "culture-translator",
      title: "The Culture Translator",
      desc: "Launching across markets? Here's what lands, what breaks, and what will get you cancelled. Market-by-market cultural adaptation intelligence.",
      icon: "\uD83C\uDF0D",
      color: "#006064",
    },
    {
      id: "social-strategist",
      title: "The Social Strategist",
      desc: "What's actually working on social this week. Which hooks stop the scroll, which trends to ride, which to skip. Tactical intelligence, not best practices from last quarter.",
      icon: "\uD83D\uDCF1",
      color: "#880E4F",
    },
    {
      id: "seo-strategist",
      title: "The SEO Strategist",
      desc: "Predicts what people will search for before keyword tools catch up. Finds the gaps, maps the clusters, and owns the rankings while competitors wait for last month's data.",
      icon: "\uD83D\uDD0E",
      color: "#33691E",
    },
    {
      id: "paid-media-strategist",
      title: "The Paid Media Strategist",
      desc: "Channel mix, budget allocation, creative rotation, and honest incrementality. Tells you where every paid dollar goes — and which platforms are a tax, not a strategy.",
      icon: "\uD83D\uDCB0",
      color: "#4E342E",
    },
    {
      id: "funnel-doctor",
      title: "The Funnel Doctor",
      desc: "Finds where your funnel is leaking, why, and what to fix first. A stage-by-stage x-ray with an impact-times-effort fix list you can start on tomorrow.",
      icon: "\uD83E\uDE7A",
      color: "#BF360C",
    },
    {
      id: "lifecycle-strategist",
      title: "The Lifecycle Strategist",
      desc: "Triggered journeys from onboarding to win-back. CRM, email, and SMS plays designed around customer state — not campaign calendars.",
      icon: "\uD83D\uDD04",
      color: "#1A237E",
    },
    {
      id: "experimentation-strategist",
      title: "The Experimentation Strategist",
      desc: "Falsifiable hypotheses, pre-registered decision rules, and a 90-day test roadmap. Fewer tests, better-designed, with actual learnings instead of vibes.",
      icon: "\uD83E\uDDEA",
      color: "#4527A0",
    },
    {
      id: "referral-architect",
      title: "The Referral Architect",
      desc: "Designs the loop before the incentive. Finds your real share moment, maps the mechanic, and engineers word-of-mouth that doesn't depend on a coupon at checkout.",
      icon: "\uD83D\uDD17",
      color: "#AD1457",
    },
    {
      id: "creative-council",
      title: "The Global Creative Council",
      desc: "Award-show entry strategist. Tells you which Cannes, Effie, Clio, D&AD, and One Show categories give your work its best shot — with a dark horse pick and the categories to skip. Not a win predictor, a strategic filter.",
      icon: "\uD83C\uDFC6",
      color: "#B8860B",
    },
    {
      id: "focus-group",
      title: "The Focus Group",
      desc: "Pre-research gut check grounded in live cultural signals. Convenes a synthetic panel anchored in what real audiences are talking about this week. Directional, not a substitute for real research.",
      icon: "\uD83D\uDDE3\uFE0F",
      color: "#00695C",
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
      .ml-section-header {
        font-size: 18px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        color: #2D2D2D;
        margin-bottom: 20px;
        margin-top: 8px;
        display: flex;
        align-items: center;
        gap: 12px;
      }
      .ml-section-header::before {
        content: "";
        display: inline-block;
        width: 28px;
        height: 3px;
        background: #6B46C1;
        border-radius: 2px;
      }
      .ml-section-header:not(:first-child) {
        padding-top: 72px;
        margin-top: 0;
      }
      .ml-agents-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 16px;
        margin-bottom: 8px;
      }
      @media (max-width: 640px) {
        .ml-agents-grid { grid-template-columns: 1fr; }
        #ml-marketplace { padding: 12px; }
      }
      .ml-agent-card {
        border: 1px solid rgba(0, 0, 0, 0.12) !important;
        border-radius: 12px !important;
        padding: 36px 32px !important;
        cursor: pointer;
        transition: all 0.2s ease;
        background: rgba(0, 0, 0, 0.04) !important;
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
        background: rgba(0, 0, 0, 0.03) !important;
        border: 1px solid rgba(0, 0, 0, 0.08) !important;
        border-radius: 12px !important;
        padding: 36px 32px !important;
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
        margin-bottom: 32px;
      }
      .ml-field {
        margin-bottom: 18px;
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
      .ml-chain-btn {
        display: inline-block;
        margin-top: 16px;
        padding: 10px 20px;
        font-family: 'Space Grotesk', sans-serif;
        font-size: 13px;
        font-weight: 500;
        color: #fff;
        background: linear-gradient(135deg, #283593, #6B46C1);
        border: none;
        border-radius: 8px;
        cursor: pointer;
        transition: opacity 0.2s ease;
      }
      .ml-chain-btn:hover { opacity: 0.85; }
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

    // Agent cards — split into four sections
    const agencyAgents = AGENTS.slice(0, 6);
    const toolkitAgents = AGENTS.slice(6, 10);
    const specialistAgents = AGENTS.slice(10, 18);
    const growthAgents = AGENTS.slice(18, 24);
    const juryAgents = AGENTS.slice(24);
    const allCards = [];

    function buildGrid(agents) {
      const grid = document.createElement("div");
      grid.className = "ml-agents-grid";
      agents.forEach((agent) => {
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
          allCards.forEach((c) => c.classList.remove("ml-selected"));
          card.classList.add("ml-selected");
          selectedAgent = agent.id;
          formSection.classList.add("ml-visible");
          formTitle.textContent = agent.title;
          submitBtn.textContent = `Generate ${agent.title} Brief`;
          statusEl.className = "ml-status";
          statusEl.style.display = "none";

          // Update placeholders for this agent
          const ph = agentPlaceholders[agent.id] || defaultPlaceholders;
          Object.keys(defaultPlaceholders).forEach((key) => {
            if (inputs[key]) inputs[key].placeholder = ph[key] || defaultPlaceholders[key];
          });

          // Auto-fill from Ask Moodlight brief fields if available
          if (window._mlParsedBriefFields) {
            Object.keys(window._mlParsedBriefFields).forEach((key) => {
              if (inputs[key]) inputs[key].value = window._mlParsedBriefFields[key];
            });
          }

          // Scroll the form into view and focus first input so users
          // don't have to hunt for where the form appeared
          setTimeout(function () {
            formSection.scrollIntoView({ behavior: "smooth", block: "center" });
            if (inputs.product) {
              try { inputs.product.focus({ preventScroll: true }); } catch (e) { inputs.product.focus(); }
            }
          }, 50);
        });
        allCards.push(card);
        grid.appendChild(card);
      });
      return grid;
    }

    const agencyHeader = document.createElement("div");
    agencyHeader.className = "ml-section-header";
    agencyHeader.textContent = "The Agency";

    const toolkitHeader = document.createElement("div");
    toolkitHeader.className = "ml-section-header";
    toolkitHeader.style.paddingTop = "72px";
    toolkitHeader.textContent = "The Toolkit";

    const specialistHeader = document.createElement("div");
    specialistHeader.className = "ml-section-header";
    specialistHeader.style.paddingTop = "72px";
    specialistHeader.textContent = "The Specialists";

    const growthHeader = document.createElement("div");
    growthHeader.className = "ml-section-header";
    growthHeader.style.paddingTop = "72px";
    growthHeader.textContent = "The Growth Team";

    const juryHeader = document.createElement("div");
    juryHeader.className = "ml-section-header";
    juryHeader.style.paddingTop = "72px";
    juryHeader.textContent = "The Jury Room";

    const agencyGrid = buildGrid(agencyAgents);
    const toolkitGrid = buildGrid(toolkitAgents);
    const specialistGrid = buildGrid(specialistAgents);
    const growthGrid = buildGrid(growthAgents);
    const juryGrid = buildGrid(juryAgents);

    // Form section
    const formSection = document.createElement("div");
    formSection.className = "ml-form-section";

    const formTitle = document.createElement("h3");
    formTitle.textContent = "";

    const subtitle = document.createElement("div");
    subtitle.className = "ml-subtitle";
    subtitle.innerHTML = 'The more detail you provide, the better your brief. <span style="color:rgba(107,70,193,0.7)">Not sure what to enter? Use Ask Moodlight above to build your prompt.</span>';

    const defaultPlaceholders = {
      product: "e.g. premium running shoe, fintech app, whiskey brand",
      audience: "e.g. women 25-40, urban professionals",
      markets: "e.g. US, UK, Canada",
      challenge: "e.g. competing against On and Hoka, launching into a saturated market",
      timeline: "e.g. Q2 2026, $2M digital",
    };

    const agentPlaceholders = {
      "brand-auditor": {
        product: "e.g. Nike, Patagonia, Oatly, your brand name",
        audience: "e.g. your primary customer segment",
        markets: "e.g. US, UK, global",
        challenge: "e.g. losing share to competitors, culturally invisible, repositioning",
        timeline: "e.g. need positioning by Q3",
      },
      "brief-critic": {
        product: "Paste your brief or strategy here — the more detail, the sharper the review",
        audience: "Who was this brief written for?",
        markets: "Target markets from the original brief",
        challenge: "Any specific concerns about the brief you want addressed",
        timeline: "When does this need to go live?",
      },
      "trend-forecaster": {
        product: "e.g. athletic wear, plant-based food, fintech, your category",
        audience: "e.g. Gen Z, working parents, luxury consumers",
        markets: "e.g. US, Europe, global",
        challenge: "e.g. what cultural shifts should we prepare for, where is the category headed",
        timeline: "e.g. planning for Q3-Q4 2026",
      },
      "copywriter": {
        product: "e.g. Nike Air Max, Oatly oat milk, or paste a brief from another agent",
        audience: "e.g. women 25-40, urban professionals",
        markets: "e.g. US, UK, social-first",
        challenge: "e.g. launch campaign, rebrand, social content series, or paste strategy output here",
        timeline: "e.g. need assets by next week",
      },
      "crisis-advisor": {
        product: "e.g. Nike, your brand — and describe the situation",
        audience: "e.g. who's angry, who's amplifying",
        markets: "e.g. US, global, specific platform",
        challenge: "e.g. viral social media backlash, product recall, executive controversy",
        timeline: "e.g. this is happening RIGHT NOW, broke 2 hours ago",
      },
      "audience-profiler": {
        product: "e.g. Nike, Peloton, your brand or category",
        audience: "e.g. who you think your audience is (we'll tell you who it actually is)",
        markets: "e.g. US, UK, global",
        challenge: "e.g. audience is aging out, need to reach new segment, don't know who's buying",
        timeline: "e.g. planning next campaign cycle",
      },
      "competitive-scout": {
        product: "e.g. name your competitor or competitive set (Nike vs. On vs. Hoka)",
        audience: "e.g. the shared audience you're fighting over",
        markets: "e.g. US, UK, global",
        challenge: "e.g. losing share, new entrant disrupting, need competitive positioning",
        timeline: "e.g. need intelligence for Q2 planning",
      },
      "pitch-builder": {
        product: "e.g. the brand you're pitching, or paste output from another agent",
        audience: "e.g. the client stakeholders in the room",
        markets: "e.g. campaign markets",
        challenge: "e.g. new business pitch, rebranding pitch, campaign extension, paste a brief here",
        timeline: "e.g. pitch is next Tuesday",
      },
      "content-strategist": {
        product: "e.g. Nike, your brand — what you sell and who you are",
        audience: "e.g. your content audience, not just buyers",
        markets: "e.g. US, global, platform-specific",
        challenge: "e.g. content isn't landing, need new pillars, launching a new channel",
        timeline: "e.g. need 30-day content plan",
      },
      "culture-translator": {
        product: "e.g. your brand + the campaign or brief to adapt",
        audience: "e.g. same audience, different market",
        markets: "e.g. US → UK + Japan, or list all target markets",
        challenge: "e.g. global launch, campaign adaptation, cultural risk assessment",
        timeline: "e.g. launching in new markets Q3",
      },
      "seo-strategist": {
        product: "e.g. Nike, your brand or category — what you want to rank for",
        audience: "e.g. who's searching, what they're looking for",
        markets: "e.g. US, UK, global",
        challenge: "e.g. no organic traffic, losing rankings to competitors, entering new category",
        timeline: "e.g. need rankings within 90 days, Q3 content plan",
      },
      "social-strategist": {
        product: "e.g. Nike, your brand — what you sell and your social presence",
        audience: "e.g. Gen Z on TikTok, professionals on LinkedIn",
        markets: "e.g. US, global, platform-specific",
        challenge: "e.g. low engagement, need to grow followers, launching on a new platform",
        timeline: "e.g. need this week's social plan",
      },
      "data-strategist": {
        product: "e.g. Nike, your brand — what you sell and what you're trying to measure",
        audience: "e.g. customer segments you want to instrument or activate",
        markets: "e.g. US, UK, global",
        challenge: "e.g. dashboard graveyard, can't prove ROI, first-party data is thin, need a learning agenda",
        timeline: "e.g. need a measurement plan in 30 days",
      },
      "creative-technologist": {
        product: "e.g. your brand + the concept you want to build, or paste a brief from another agent",
        audience: "e.g. who will experience the thing you're building",
        markets: "e.g. US, global, platform-specific",
        challenge: "e.g. can we actually build this, what stack do we need, prototype before we commit, what will break",
        timeline: "e.g. need a working prototype in 3 weeks",
      },
      "paid-media-strategist": {
        product: "e.g. Nike, your brand — what you're trying to acquire or promote",
        audience: "e.g. who you're buying media against",
        markets: "e.g. US, UK, global",
        challenge: "e.g. CPA climbing, creative fatigue, need to pick channels, ROAS vs. incrementality gap",
        timeline: "e.g. Q2 plan, $500K budget, need a 30-60-90 deployment",
      },
      "funnel-doctor": {
        product: "e.g. Nike, your brand or product — what you're trying to convert",
        audience: "e.g. the traffic that isn't converting",
        markets: "e.g. US, UK, global",
        challenge: "e.g. checkout abandonment, traffic doesn't convert, activation broken, low repeat purchase",
        timeline: "e.g. need a prioritized fix list this week",
      },
      "lifecycle-strategist": {
        product: "e.g. Nike, your brand — what your customers buy or subscribe to",
        audience: "e.g. your customer base across lifecycle stages",
        markets: "e.g. US, UK, global",
        challenge: "e.g. churn is rising, onboarding isn't activating, need a win-back sequence, silo'd CRM",
        timeline: "e.g. need a 90-day lifecycle build roadmap",
      },
      "experimentation-strategist": {
        product: "e.g. Nike, your brand — what you want to test and learn",
        audience: "e.g. the audience the test will run against",
        markets: "e.g. US, UK, global",
        challenge: "e.g. running tests without hypotheses, need a test roadmap, can't tell winners from noise",
        timeline: "e.g. 90-day experimentation program",
      },
      "referral-architect": {
        product: "e.g. Nike, your brand — what you want customers to share",
        audience: "e.g. your most loyal customers, your hero-moment users",
        markets: "e.g. US, UK, global",
        challenge: "e.g. no organic word-of-mouth, referral program is flat, need to design a loop from scratch",
        timeline: "e.g. need a referral program live in 90 days",
      },
      "partnership-scout": {
        product: "e.g. Nike, your brand — what cultural gap you're trying to close through a partner",
        audience: "e.g. the audience you want to reach or borrow credibility with",
        markets: "e.g. US, UK, global",
        challenge: "e.g. need to borrow cultural credit, looking for unexpected collabs, bored of the usual co-brand suspects",
        timeline: "e.g. need a partnership live by Q3 launch",
      },
      "creative-council": {
        product: "Paste your case study here — the work, what it did, the evidence. The more complete, the sharper the read.",
        audience: "e.g. the audience the work was made for",
        markets: "e.g. where the work ran — US, UK, global",
        challenge: "e.g. which Cannes categories, Effie fit check, pro-bono film strategy, where should this work compete",
        timeline: "e.g. 2026 eligibility, $40K awards budget",
      },
      "focus-group": {
        product: "Paste the creative — script, copy, concept, tagline. Describe the visual if it's not text.",
        audience: "e.g. women 28-40 urban beauty enthusiasts — OR leave blank to auto-select from brand",
        markets: "e.g. US, UK — where this creative will run",
        challenge: "e.g. does this tagline read too clinical, pre-launch gut check, messaging test before we spend on real research",
        timeline: "e.g. launching in 6 weeks, pre-production gut check",
      },
    };

    const fields = [
      { name: "product", label: "Product / Service", placeholder: defaultPlaceholders.product, required: true },
      { name: "audience", label: "Target Audience", placeholder: defaultPlaceholders.audience },
      { name: "markets", label: "Markets / Geography", placeholder: defaultPlaceholders.markets },
      { name: "challenge", label: "Key Challenge", placeholder: defaultPlaceholders.challenge },
      { name: "timeline", label: "Timeline / Budget", placeholder: defaultPlaceholders.timeline },
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
          const chainHtml = selectedAgent !== "copywriter"
            ? '<button class="ml-chain-btn" id="ml-chain-copywriter">\u270D\uFE0F Send to Copywriter</button>'
            : "";
          previewSection.innerHTML = `
            <div class="ml-preview-wrap">
              <div class="ml-preview-text">${data.preview.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}</div>
              <div class="ml-preview-fade"></div>
            </div>
            <div class="ml-preview-cta">
              <div class="ml-cta-main">Full brief sent to ${email}</div>
              <div class="ml-cta-sub">Check your inbox — the complete analysis is waiting for you.</div>
              ${chainHtml}
            </div>
          `;
          previewSection.classList.add("ml-visible");
          previewSection.scrollIntoView({ behavior: "smooth", block: "start" });

          // Wire up chain button
          const chainBtn = document.getElementById("ml-chain-copywriter");
          if (chainBtn) {
            chainBtn.addEventListener("click", () => {
              // Select the Copywriter card
              const copywriterCard = allCards.find((c) => c.querySelector("h3")?.textContent === "The Copywriter");
              if (copywriterCard) {
                allCards.forEach((c) => c.classList.remove("ml-selected"));
                copywriterCard.classList.add("ml-selected");
                selectedAgent = "copywriter";
                formSection.classList.add("ml-visible");
                formTitle.textContent = "The Copywriter";
                submitBtn.textContent = "Generate The Copywriter Brief";
                submitBtn.disabled = false;
                statusEl.className = "ml-status";
                statusEl.style.display = "none";
                previewSection.className = "ml-preview-section";

                // Fill challenge field with previous output
                inputs.challenge.value = data.preview;

                // Scroll to form
                formSection.scrollIntoView({ behavior: "smooth", block: "start" });
              }
            });
          }
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

    container.appendChild(agencyHeader);
    container.appendChild(agencyGrid);
    container.appendChild(toolkitHeader);
    container.appendChild(toolkitGrid);
    container.appendChild(specialistHeader);
    container.appendChild(specialistGrid);
    container.appendChild(growthHeader);
    container.appendChild(growthGrid);
    container.appendChild(juryHeader);
    container.appendChild(juryGrid);
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
