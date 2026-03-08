import type { Tier, FeatureName } from "./types";

// ── API ───────────────────────────────────────────────

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "https://moodlight-api-production.up.railway.app";

// ── Active tiers ──────────────────────────────────────

export const ACTIVE_TIERS: Tier[] = [
  "monthly",
  "annually",
  "professional",
  "enterprise",
];

// ── Feature gating (mirrors tier_helper.py) ───────────

export const TIER_FEATURES: Record<FeatureName, Tier[]> = {
  competitive_war_room: [...ACTIVE_TIERS],
  intelligence_reports: [...ACTIVE_TIERS],
  ask_moodlight: [...ACTIVE_TIERS],
  intelligence_dashboard: [...ACTIVE_TIERS],
  prediction_markets: [...ACTIVE_TIERS],
  strategic_brief: [...ACTIVE_TIERS],
  brand_watchlist: [...ACTIVE_TIERS],
  topic_watchlist: [...ACTIVE_TIERS],
  brand_focus: [...ACTIVE_TIERS],
  competitive_tracking: [...ACTIVE_TIERS],
};

export const TIER_LIMITS = {
  brand_watchlist_max: 5,
  topic_watchlist_max: 10,
} as const;

// ── Severity icons ────────────────────────────────────

export const SEVERITY_ICONS: Record<string, string> = {
  critical: "\uD83D\uDD34",
  warning: "\uD83D\uDFE1",
  info: "\uD83D\uDD35",
  correlation: "\uD83D\uDD17",
  prediction: "\uD83D\uDD2E",
};

// ── Empathy labels ────────────────────────────────────

export function getEmpathyLabel(score: number): string {
  if (score < 35) return "Very Cold/Hostile";
  if (score < 50) return "Detached/Neutral";
  if (score < 70) return "Warm/Supportive";
  return "Highly Empathetic";
}

export function getEmpathyEmoji(score: number): string {
  if (score < 35) return "\u2744\uFE0F";
  if (score < 50) return "\uD83D\uDE10";
  if (score < 70) return "\uD83D\uDE0A";
  return "\u2764\uFE0F";
}

// ── Market index display names ────────────────────────

export const MARKET_SYMBOLS: Record<string, string> = {
  SPY: "S&P 500",
  QQQ: "NASDAQ 100",
  DIA: "Dow Jones",
  IWM: "Russell 2000",
  EWU: "UK (FTSE)",
  EWJ: "Japan (Nikkei)",
  EWG: "Germany (DAX)",
  FXI: "China (CSI)",
};

// ── Economic indicator display ────────────────────────

export const ECONOMIC_INDICATORS: Record<
  string,
  { label: string; unit: string; format: "percent" | "number" | "currency" }
> = {
  "CPI": { label: "CPI (YoY)", unit: "%", format: "percent" },
  "Federal Funds Rate": { label: "Fed Funds Rate", unit: "%", format: "percent" },
  "10-Year Treasury": { label: "10Y Treasury", unit: "%", format: "percent" },
  "Unemployment Rate": { label: "Unemployment", unit: "%", format: "percent" },
  "Inflation Rate": { label: "Inflation Rate", unit: "%", format: "percent" },
  "Nonfarm Payroll": { label: "Nonfarm Payroll", unit: "", format: "number" },
};

// ── Commodity display ─────────────────────────────────

export const COMMODITY_NAMES: Record<string, string> = {
  "WTI Crude Oil": "WTI Crude",
  "Brent Crude Oil": "Brent Crude",
  Copper: "Copper",
  Aluminum: "Aluminum",
  "Natural Gas": "Natural Gas",
};

// ── Colors (Streamlit-inspired dark theme) ────────────

export const COLORS = {
  background: "#0E1117",
  surface: "#262730",
  surfaceLight: "#3B3B4F",
  border: "#3B3B4F",
  text: "#FAFAFA",
  textMuted: "#8B8B9E",
  primary: "#FF4B4B",
  success: "#21C354",
  warning: "#FACA15",
  error: "#FF4B4B",
  info: "#60A5FA",
  chart: [
    "#FF4B4B",
    "#60A5FA",
    "#21C354",
    "#FACA15",
    "#A78BFA",
    "#F472B6",
    "#34D399",
    "#FB923C",
  ],
} as const;

// ── Topic categories (matches app.py _TOPIC_CATEGORIES) ─

export const TOPIC_CATEGORIES = [
  "politics",
  "government",
  "economics",
  "education",
  "culture & identity",
  "branding & advertising",
  "creative & design",
  "technology & ai",
  "climate & environment",
  "healthcare & wellbeing",
  "immigration",
  "crime & safety",
  "war & foreign policy",
  "media & journalism",
  "race & ethnicity",
  "gender & sexuality",
  "business & corporate",
  "labor & work",
  "housing",
  "religion & values",
  "sports",
  "entertainment",
];

// ── Alert type categories ─────────────────────────────

export const ALERT_TYPE_CATEGORIES: Record<string, string[]> = {
  brand: [
    "brand_white_space",
    "brand_velocity_spike",
    "brand_narrative_fading",
    "brand_saturation",
    "brand_mention_surge",
    "brand_sentiment_shift",
    "brand_crisis",
  ],
  topic: [
    "topic_mention_surge",
    "topic_sentiment_shift",
    "topic_intensity_spike",
    "topic_velocity_spike",
    "topic_saturation",
  ],
  global: [
    "mood_shift",
    "market_mood_divergence",
    "intensity_cluster",
    "topic_emergence",
    "regulatory_policy_spike",
    "breaking_signal",
    "geopolitical_risk_escalation",
  ],
  predictive: [
    "predictive_mood_shift",
    "predictive_intensity_cluster",
    "predictive_brand_velocity_spike",
    "predictive_brand_saturation",
    "predictive_brand_white_space",
    "predictive_market_mood_divergence",
    "predictive_compound_signal",
    "predictive_topic_velocity_spike",
    "predictive_topic_saturation",
  ],
  competitive: [
    "competitor_momentum",
    "share_of_voice_shift",
    "competitive_white_space",
  ],
};
