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

  // tier: "upstream" (analysis/strategy/research — runs first),
  //       "downstream" (production/making the artifact — runs after
  //       context is set), "both" (agents that operate on either side
  //       of the chain depending on the query), or "bundle" (multi-
  //       agent packages that contain their own upstream→downstream
  //       flow). Used for the tier badge on each card and for Ship 3
  //       sequence validation in the routing parser.
  const AGENTS = [
    {
      id: "new-business-win",
      title: "New Business Win",
      desc: "Integrates six agents into one pitch package: Brand Auditor, Audience Profiler, Pitch Strategist, Pitch Builder, Copywriter, and the Global Creative Council. Diagnostic → real audience → the one strategic insight → winning narrative → the lines that sell it → award-show endgame. For agencies walking into a pitch room.",
      icon: "\uD83C\uDFC6",
      color: "#8E24AA",
      tier: "bundle",
    },
    {
      id: "outbound-discovery",
      title: "Outbound Discovery",
      desc: "Integrates four agents into one GTM motion: GTM Researcher, Competitive Scout, Audience Profiler, and a B2B Copywriter. Finds the next 10 accounts in motion, maps the category, reads the buyer culturally, and writes outbound lines you can send today. For operators without a BDR army.",
      icon: "\uD83C\uDFAF",
      color: "#00897B",
      tier: "bundle",
    },
    {
      id: "cco",
      title: "The Chief Creative Officer",
      desc: "Builds campaign concepts from live cultural signals. The brief it writes on Tuesday is different from the one it writes on Thursday. Because the culture moved.",
      icon: "\u2728",
      color: "#7B1FA2",
      tier: "downstream",
    },
    {
      id: "cso",
      title: "The Cultural Strategist",
      desc: "Reads the market, the mood, and the momentum. Picks a position. Defends it with data. Doesn't hedge.",
      icon: "\u265F",
      color: "#1565C0",
      tier: "upstream",
    },
    {
      id: "comms-planner",
      title: "The Comms Planner",
      desc: "Tells you where to show up, when to deploy, and what to skip. Every recommendation backed by where attention actually is.",
      icon: "\uD83D\uDCE1",
      color: "#2E7D32",
      tier: "upstream",
    },
    {
      id: "full-deploy",
      title: "Full Deploy",
      desc: "All three working as one team. One input, one complete battle plan: strategy, creative, and distribution that don't contradict each other.",
      icon: "\uD83D\uDE80",
      color: "#D84315",
      premium: true,
      tier: "bundle",
    },
    {
      id: "data-strategist",
      title: "The Data Strategist",
      desc: "Builds the KPI tree, kills the vanity metrics, and tells you which first-party data to activate. A measurement plan that actually ladders to revenue — not a dashboard graveyard.",
      icon: "\uD83D\uDCCA",
      color: "#37474F",
      tier: "upstream",
    },
    {
      id: "creative-technologist",
      title: "The Creative Technologist",
      desc: "Translates a concept into a stack, a prototype, and a build plan. Tells you what to build, what to buy, what will break, and when to walk away. No hype — just what ships.",
      icon: "\uD83D\uDEE0\uFE0F",
      color: "#5D4037",
      tier: "downstream",
    },
    {
      id: "brand-auditor",
      title: "The Brand Auditor",
      desc: "Type your brand. See where you stand culturally — what you own, what you're missing, and where the whitespace is. A full diagnostic in 60 seconds.",
      icon: "\uD83D\uDD0D",
      color: "#00838F",
      tier: "upstream",
    },
    {
      id: "brief-critic",
      title: "The Brief Critic",
      desc: "Paste your brief. Get it torn apart against live data. Finds what's stale, what's wrong, and what the data says you should be doing instead.",
      icon: "\u2702\uFE0F",
      color: "#AD1457",
      tier: "both",
    },
    {
      id: "trend-forecaster",
      title: "The Trend Forecaster",
      desc: "Not what's trending now — what's next. Reads velocity, scarcity, and signal clusters to predict cultural shifts before they have names.",
      icon: "\uD83D\uDD2E",
      color: "#E65100",
      tier: "upstream",
    },
    {
      id: "copywriter",
      title: "The Copywriter",
      desc: "Headlines, social posts, and ad copy tuned to the cultural moment. Every line is built on what's happening right now, not what was approved last month.",
      icon: "\u270D\uFE0F",
      color: "#283593",
      tier: "downstream",
    },
    {
      id: "crisis-advisor",
      title: "The Crisis Advisor",
      desc: "Your brand just got tagged in something. Here's what to say, what not to say, and how fast you need to move. Real-time crisis response, not a PR playbook.",
      icon: "\u26A1",
      color: "#B71C1C",
      tier: "both",
    },
    {
      id: "audience-profiler",
      title: "The Audience Profiler",
      desc: "Who's actually talking about your brand, what they care about, and where they're drifting. Psychographic intelligence from live signals, not stale persona decks.",
      icon: "\uD83C\uDFAF",
      color: "#4A148C",
      tier: "upstream",
    },
    {
      id: "competitive-scout",
      title: "The Competitive Scout",
      desc: "What cultural territory your competitors are claiming, where they're vulnerable, and what they're sleeping on. Head-to-head intelligence from live data.",
      icon: "\uD83D\uDD75\uFE0F",
      color: "#1B5E20",
      tier: "upstream",
    },
    {
      id: "partnership-scout",
      title: "The Partnership Scout",
      desc: "The opposite of the Competitive Scout. Finds unexpected brand, creator, and institution collabs — with the value exchange, the risk read, and how to actually make the ask.",
      icon: "\uD83E\uDD1D",
      color: "#6A1B9A",
      tier: "upstream",
    },
    {
      id: "pitch-builder",
      title: "The Pitch Builder",
      desc: "Turns any brief or strategy into a client-ready pitch narrative. The insight that wins the room, the setup that makes inaction feel dangerous.",
      icon: "\uD83C\uDFAC",
      color: "#F57F17",
      tier: "downstream",
    },
    {
      id: "pitch-strategist",
      title: "The Pitch Strategist",
      desc: "The planner who walks into the room with the brief already solved. Takes diagnosis and audience and hands you the one strategic insight the pitch lives or dies on. Not three options — a bet. Kills clever for inevitable.",
      icon: "\uD83D\uDDFA\uFE0F",
      color: "#283593",
      tier: "upstream",
    },
    {
      id: "content-strategist",
      title: "The Content Strategist",
      desc: "Content pillars, editorial rhythm, and platform angles built from what the culture is actually talking about. Not a calendar — a content ecosystem.",
      icon: "\uD83D\uDCDD",
      color: "#0277BD",
      tier: "upstream",
    },
    {
      id: "culture-translator",
      title: "The Culture Translator",
      desc: "Launching across markets? Here's what lands, what breaks, and what will get you cancelled. Market-by-market cultural adaptation intelligence.",
      icon: "\uD83C\uDF0D",
      color: "#006064",
      tier: "upstream",
    },
    {
      id: "social-strategist",
      title: "The Social Strategist",
      desc: "What's actually working on social this week. Which hooks stop the scroll, which trends to ride, which to skip. Tactical intelligence, not best practices from last quarter.",
      icon: "\uD83D\uDCF1",
      color: "#880E4F",
      tier: "both",
    },
    {
      id: "gtm-researcher",
      title: "The GTM Researcher",
      desc: "Tells you exactly who to go after this week. 10 account archetypes, the trigger signals worth hunting, the ICP that fits a LinkedIn filter — and which categories to skip. The research brief every growth team needs before outbound starts.",
      icon: "\uD83D\uDD2D",
      color: "#2E7D32",
      tier: "upstream",
    },
    {
      id: "seo-strategist",
      title: "The SEO Strategist",
      desc: "Predicts what people will search for before keyword tools catch up. Finds the gaps, maps the clusters, and owns the rankings while competitors wait for last month's data.",
      icon: "\uD83D\uDD0E",
      color: "#33691E",
      tier: "both",
    },
    {
      id: "paid-media-strategist",
      title: "The Paid Media Strategist",
      desc: "Channel mix, budget allocation, creative rotation, and honest incrementality. Tells you where every paid dollar goes — and which platforms are a tax, not a strategy.",
      icon: "\uD83D\uDCB0",
      color: "#4E342E",
      tier: "both",
    },
    {
      id: "funnel-doctor",
      title: "The Funnel Doctor",
      desc: "Finds where your funnel is leaking, why, and what to fix first. A stage-by-stage x-ray with an impact-times-effort fix list you can start on tomorrow.",
      icon: "\uD83E\uDE7A",
      color: "#BF360C",
      tier: "both",
    },
    {
      id: "lifecycle-strategist",
      title: "The Lifecycle Strategist",
      desc: "Triggered journeys from onboarding to win-back. CRM, email, and SMS plays designed around customer state — not campaign calendars.",
      icon: "\uD83D\uDD04",
      color: "#1A237E",
      tier: "both",
    },
    {
      id: "experimentation-strategist",
      title: "The Experimentation Strategist",
      desc: "Falsifiable hypotheses, pre-registered decision rules, and a 90-day test roadmap. Fewer tests, better-designed, with actual learnings instead of vibes.",
      icon: "\uD83E\uDDEA",
      color: "#4527A0",
      tier: "both",
    },
    {
      id: "referral-architect",
      title: "The Referral Architect",
      desc: "Designs the loop before the incentive. Finds your real share moment, maps the mechanic, and engineers word-of-mouth that doesn't depend on a coupon at checkout.",
      icon: "\uD83D\uDD17",
      color: "#AD1457",
      tier: "both",
    },
    {
      id: "creative-council",
      title: "The Global Creative Council",
      desc: "Award-show entry strategist. Grounded in the top global advertising shows (Cannes, Effie, Clio, D&AD, One Show, ADC, LIA) AND the historical database of past winning work and the exact categories it won in.",
      icon: "\uD83C\uDFC6",
      color: "#B8860B",
      tier: "upstream",
    },
    {
      id: "focus-group",
      title: "The Focus Group",
      desc: "Pre-research gut check grounded in live cultural signals. Convenes a synthetic panel anchored in what real audiences are talking about this week. Directional, not a substitute for real research.",
      icon: "\uD83D\uDDE3\uFE0F",
      color: "#00695C",
      tier: "upstream",
    },
  ];

  // Display label + color-pair for each tier. Kept separate from the
  // raw tier so we can swap copy without retyping 30 metadata blocks.
  const TIER_DISPLAY = {
    upstream:   { label: "Analysis",   color: "#1565C0" },
    downstream: { label: "Production", color: "#D84315" },
    both:       { label: "Hybrid",     color: "#5D4037" },
    bundle:     { label: "Bundle",     color: "#8E24AA" },
  };

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
        top: 14px;
        right: 14px;
        color: #6B46C1;
        font-size: 10px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.8px;
      }
      .ml-tier-badge {
        position: absolute;
        top: 14px;
        right: 14px;
        font-size: 10px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        opacity: 0.55;
      }
      .ml-agent-card:hover .ml-tier-badge { opacity: 0.9; }
      .ml-form-section {
        display: none;
        background: rgba(0, 0, 0, 0.03) !important;
        border: 1px solid rgba(0, 0, 0, 0.08) !important;
        border-radius: 12px !important;
        padding: 36px 32px !important;
        margin-bottom: 24px;
      }
      .ml-form-section.ml-visible { display: block; }
      .ml-brief-banner {
        display: none;
        background: rgba(123, 31, 162, 0.06);
        border: 1px solid rgba(123, 31, 162, 0.18);
        border-radius: 10px;
        padding: 12px 16px;
        margin-bottom: 20px;
        font-size: 13px;
        color: #2D2D2D;
        display: flex;
        align-items: flex-start;
        gap: 12px;
      }
      .ml-brief-banner.ml-visible { display: flex; }
      .ml-brief-banner-body {
        flex: 1;
        line-height: 1.5;
      }
      .ml-brief-banner-label {
        font-weight: 600;
        color: #7B1FA2;
        display: block;
        margin-bottom: 2px;
      }
      .ml-brief-banner-quote {
        color: rgba(45, 45, 45, 0.75);
        font-style: italic;
      }
      .ml-brief-banner-clear {
        background: none;
        border: none;
        color: #7B1FA2;
        font-size: 12px;
        font-weight: 500;
        cursor: pointer;
        padding: 4px 8px;
        white-space: nowrap;
        text-decoration: underline;
        align-self: center;
      }
      .ml-brief-banner-clear:hover { color: #5a1480; }
      .ml-context-card {
        display: none;
        background: rgba(123, 31, 162, 0.04);
        border: 1px dashed rgba(123, 31, 162, 0.28);
        border-radius: 10px;
        padding: 12px 16px;
        margin-bottom: 20px;
        font-size: 13px;
        color: #2D2D2D;
      }
      .ml-context-card.ml-visible { display: block; }
      .ml-context-label {
        font-weight: 600;
        color: #7B1FA2;
        display: block;
        margin-bottom: 8px;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.4px;
      }
      .ml-context-chips {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }
      .ml-context-chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(123, 31, 162, 0.10);
        color: #5a1480;
        border-radius: 999px;
        padding: 4px 10px 4px 12px;
        font-size: 12px;
        font-weight: 500;
      }
      .ml-context-chip-remove {
        background: none;
        border: none;
        color: #7B1FA2;
        font-size: 14px;
        line-height: 1;
        cursor: pointer;
        padding: 0 0 0 2px;
        font-weight: 700;
      }
      .ml-context-chip-remove:hover { color: #5a1480; }
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

  var SESSION_OUTPUTS_TTL_MS = 24 * 60 * 60 * 1000;

  function hydrateBriefFromStorage() {
    // Hydrate session agent outputs (Ship 2) — these persist across
    // marketplace runs so downstream agents can build on upstream
    // work without copy/paste. Keyed by agent_id.
    if (!window._mlSessionAgentOutputs) {
      try {
        var rawOut = localStorage.getItem("ml_session_agent_outputs");
        if (rawOut) {
          var parsedOut = JSON.parse(rawOut);
          var nowTs = Date.now();
          var fresh = {};
          Object.keys(parsedOut || {}).forEach(function (k) {
            var entry = parsedOut[k];
            if (entry && entry.timestamp && nowTs - entry.timestamp < SESSION_OUTPUTS_TTL_MS) {
              fresh[k] = entry;
            }
          });
          window._mlSessionAgentOutputs = fresh;
          localStorage.setItem("ml_session_agent_outputs", JSON.stringify(fresh));
        } else {
          window._mlSessionAgentOutputs = {};
        }
      } catch (e) {
        window._mlSessionAgentOutputs = {};
      }
    }

    // If the Ask Moodlight widget already set the global this
    // tab (user just clicked the CTA), leave it alone.
    if (window._mlParsedBriefFields) return;
    try {
      var stored = localStorage.getItem("ml_active_brief");
      if (!stored) return;
      var brief = JSON.parse(stored);
      // 24h expiry — stale briefs from last week shouldn't leak
      // back into a fresh session.
      if (!brief.timestamp || Date.now() - brief.timestamp > 24 * 60 * 60 * 1000) {
        localStorage.removeItem("ml_active_brief");
        return;
      }
      window._mlParsedBriefFields = brief.fields || {};
      window._mlActiveBrief = brief;
    } catch (e) {}
  }

  function persistSessionOutputs() {
    try {
      localStorage.setItem(
        "ml_session_agent_outputs",
        JSON.stringify(window._mlSessionAgentOutputs || {})
      );
    } catch (e) {}
  }

  function buildUI(container) {
    let selectedAgent = null;
    hydrateBriefFromStorage();

    // Agent cards — split into sections
    const bundleAgents = AGENTS.slice(0, 2);
    const agencyAgents = AGENTS.slice(2, 8);
    const toolkitAgents = AGENTS.slice(8, 12);
    const specialistAgents = AGENTS.slice(12, 21);
    const growthAgents = AGENTS.slice(21, 28);
    const juryAgents = AGENTS.slice(28);
    const allCards = [];

    function buildGrid(agents) {
      const grid = document.createElement("div");
      grid.className = "ml-agents-grid";
      agents.forEach((agent) => {
        const card = document.createElement("div");
        card.className = "ml-agent-card";
        card.style.setProperty("--agent-color", agent.color);
        // Tier badge — shown on every non-premium card so users can
        // instantly read whether an agent is Analysis (upstream),
        // Production (downstream), Hybrid (both), or a Bundle. The
        // "All Three" premium badge still wins on full-deploy so
        // badges don't stack in the top-right corner.
        const tier = TIER_DISPLAY[agent.tier] || null;
        const tierBadgeHTML = (!agent.premium && tier)
          ? `<span class="ml-tier-badge" style="color:${tier.color}">${tier.label}</span>`
          : "";
        card.innerHTML = `
          <span class="ml-icon">${agent.icon}</span>
          ${agent.premium ? '<span class="ml-premium-badge">All Three</span>' : tierBadgeHTML}
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

          // Show the "brief is locked" banner if we have an active
          // brief. The Ask Moodlight parse is the source of truth —
          // all agents in this session analyze the same brief.
          if (window._mlActiveBrief) {
            const q = window._mlActiveBrief.originalQuestion || "";
            const shown = q.length > 120 ? q.slice(0, 117) + "\u2026" : q;
            briefBannerQuote.textContent = shown ? ' \u201C' + shown + '\u201D' : "";
            briefBanner.classList.add("ml-visible");
          } else {
            briefBanner.classList.remove("ml-visible");
          }

          // Render upstream context chips for every prior agent run
          // in this session (excluding the currently selected one).
          renderContextChips(agent.id);

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

    const bundleHeader = document.createElement("div");
    bundleHeader.className = "ml-section-header";
    bundleHeader.textContent = "The Rainmakers";

    const agencyHeader = document.createElement("div");
    agencyHeader.className = "ml-section-header";
    agencyHeader.style.paddingTop = "72px";
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

    const bundleGrid = buildGrid(bundleAgents);
    const agencyGrid = buildGrid(agencyAgents);
    const toolkitGrid = buildGrid(toolkitAgents);
    const specialistGrid = buildGrid(specialistAgents);
    const growthGrid = buildGrid(growthAgents);
    const juryGrid = buildGrid(juryAgents);

    // Form section
    const formSection = document.createElement("div");
    formSection.className = "ml-form-section";

    // Brief banner — shown when user arrived via Ask Moodlight (or
    // a persisted brief was hydrated from localStorage). Makes the
    // "your brief travels with you across agents" model visible.
    const briefBanner = document.createElement("div");
    briefBanner.className = "ml-brief-banner";
    const briefBannerBody = document.createElement("div");
    briefBannerBody.className = "ml-brief-banner-body";
    const briefBannerLabel = document.createElement("span");
    briefBannerLabel.className = "ml-brief-banner-label";
    briefBannerLabel.textContent = "\uD83D\uDCCB Working from the brief you built with Ask Moodlight";
    const briefBannerQuote = document.createElement("span");
    briefBannerQuote.className = "ml-brief-banner-quote";
    briefBannerBody.appendChild(briefBannerLabel);
    briefBannerBody.appendChild(briefBannerQuote);
    const briefBannerClear = document.createElement("button");
    briefBannerClear.className = "ml-brief-banner-clear";
    briefBannerClear.type = "button";
    briefBannerClear.textContent = "Clear and start fresh";
    briefBanner.appendChild(briefBannerBody);
    briefBanner.appendChild(briefBannerClear);

    // Upstream context card (Ship 2) — shows chips for every agent
    // the user has already run in this session, so a downstream
    // agent (e.g. The Copywriter) visibly builds on the upstream
    // work (e.g. The Cultural Strategist) rather than starting cold.
    const contextCard = document.createElement("div");
    contextCard.className = "ml-context-card";
    const contextLabel = document.createElement("span");
    contextLabel.className = "ml-context-label";
    contextLabel.textContent = "Continuing from";
    const contextChips = document.createElement("div");
    contextChips.className = "ml-context-chips";
    contextCard.appendChild(contextLabel);
    contextCard.appendChild(contextChips);

    function renderContextChips(forAgentId) {
      contextChips.innerHTML = "";
      var outputs = window._mlSessionAgentOutputs || {};
      var ids = Object.keys(outputs).filter(function (k) { return k !== forAgentId; });
      if (!ids.length) {
        contextCard.classList.remove("ml-visible");
        return;
      }
      ids.forEach(function (id) {
        var entry = outputs[id];
        if (!entry) return;
        var chip = document.createElement("span");
        chip.className = "ml-context-chip";
        chip.textContent = entry.agent_label || id;
        var remove = document.createElement("button");
        remove.type = "button";
        remove.className = "ml-context-chip-remove";
        remove.setAttribute("aria-label", "Remove " + (entry.agent_label || id));
        remove.textContent = "\u00D7";
        remove.addEventListener("click", function (ev) {
          ev.stopPropagation();
          delete window._mlSessionAgentOutputs[id];
          persistSessionOutputs();
          renderContextChips(forAgentId);
        });
        chip.appendChild(remove);
        contextChips.appendChild(chip);
      });
      contextCard.classList.add("ml-visible");
    }

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
      "new-business-win": {
        product: "e.g. the brand you're pitching (or paste the RFP) — what they sell and what they're trying to solve",
        audience: "e.g. the audience in the RFP (we'll tell you who's actually buying)",
        markets: "e.g. US, UK, global — where the winning work would run",
        challenge: "e.g. new business pitch, incumbent defending, chemistry meeting, final-round creative presentation",
        timeline: "e.g. pitch is next Tuesday, final round in 2 weeks",
      },
      "outbound-discovery": {
        product: "e.g. what you sell — a service, a tool, a point of view. The tighter the description, the sharper the outbound.",
        audience: "e.g. the kind of buyer you want (VP Marketing at Series B D2C brands, founders of 10-50 person agencies, etc.)",
        markets: "e.g. US, UK, global — where you can actually service",
        challenge: "e.g. need to book 10 qualified calls this month, launching a new offer, breaking into a new category, pipeline is dry",
        timeline: "e.g. need lines I can send this week",
      },
      "gtm-researcher": {
        product: "e.g. what you sell — the offering you need to find accounts for",
        audience: "e.g. the type of buyer you think fits (we'll tighten the ICP against live signals)",
        markets: "e.g. US, UK, global — where you can actually service",
        challenge: "e.g. don't know who to hunt this quarter, category feels crowded, pipeline research is stale",
        timeline: "e.g. need a target list today",
      },
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
      "pitch-strategist": {
        product: "e.g. the brand you're pitching, or paste Brand Auditor + Audience Profiler output",
        audience: "e.g. the audience the pitch has to move — and who's in the room",
        markets: "e.g. the markets the work has to work in",
        challenge: "e.g. new business pitch, need one inevitable strategic insight before the creative team touches it",
        timeline: "e.g. pitch is next Tuesday, need the spine by Friday",
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
      "The Pitch Strategist is thinking...",
      "Mapping velocity, density, and scarcity...",
      "The Brand Auditor is taking the pulse...",
      "Hunting for inevitable insights...",
      "The Audience Profiler is listening...",
      "Killing clever for inevitable...",
      "The Pitch Builder is structuring the room...",
      "Running the substitution test...",
      "The Copywriter is rewriting the first line...",
      "Stripping hedge words...",
      "The Creative Council is weighing awards...",
      "Pressure-testing the spine...",
      "Checking what the competition isn't saying...",
      "The Focus Group is reacting...",
      "Building the case for why now...",
      "Defending the position...",
      "Double-checking every signal citation...",
      "Shaping the opening provocation...",
      "Refusing the three-option menu...",
      "Finalizing the brief...",
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
        stepEl.textContent = loadingSteps[stepIdx % loadingSteps.length];
      }, 6000);

      // Build upstream_context from session outputs, excluding the
      // currently selected agent (can't be upstream of itself).
      const sessionOutputs = window._mlSessionAgentOutputs || {};
      const upstreamContext = Object.keys(sessionOutputs)
        .filter((k) => k !== selectedAgent)
        .map((k) => ({
          agent_id: k,
          agent_label: sessionOutputs[k].agent_label || k,
          output: sessionOutputs[k].output || "",
        }));

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
            upstream_context: upstreamContext,
          }),
        });

        clearInterval(stepInterval);
        loadingSection.classList.remove("ml-visible");

        const data = await res.json();

        if (res.ok && data.preview) {
          // Ship 2: capture the full output so future downstream
          // agents in this session automatically inherit it as
          // upstream context. The brief form fields stay locked to
          // the Ask Moodlight source of truth — context is additive,
          // never a form-field replacement.
          if (data.full_output) {
            if (!window._mlSessionAgentOutputs) window._mlSessionAgentOutputs = {};
            window._mlSessionAgentOutputs[selectedAgent] = {
              agent_id: selectedAgent,
              agent_label: data.agent_label || selectedAgent,
              output: data.full_output,
              timestamp: Date.now(),
            };
            persistSessionOutputs();
          }
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

    formSection.appendChild(briefBanner);
    formSection.appendChild(contextCard);
    formSection.appendChild(formTitle);
    formSection.appendChild(subtitle);
    formSection.appendChild(fieldsContainer);
    formSection.appendChild(submitBtn);
    formSection.appendChild(statusEl);
    formSection.appendChild(loadingSection);
    formSection.appendChild(previewSection);

    // Clear the active brief — wipe localStorage, globals, form
    // fields, and hide the banner. User can then start fresh.
    briefBannerClear.addEventListener("click", () => {
      try { localStorage.removeItem("ml_active_brief"); } catch (e) {}
      try { localStorage.removeItem("ml_session_agent_outputs"); } catch (e) {}
      delete window._mlParsedBriefFields;
      delete window._mlActiveBrief;
      window._mlSessionAgentOutputs = {};
      Object.keys(inputs).forEach((k) => {
        if (inputs[k]) inputs[k].value = "";
      });
      briefBanner.classList.remove("ml-visible");
      contextCard.classList.remove("ml-visible");
      contextChips.innerHTML = "";
    });

    // Powered by
    const powered = document.createElement("div");
    powered.className = "ml-powered-by";
    powered.textContent = "Powered by Moodlight Real-Time Intelligence";

    container.appendChild(bundleHeader);
    container.appendChild(bundleGrid);
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
