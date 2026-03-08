// TypeScript interfaces for all Moodlight API responses

// ── Auth ──────────────────────────────────────────────

export interface LoginRequest {
  email?: string;
  username?: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  username: string;
  email: string;
  tier: Tier;
  is_admin: boolean;
  expires_in: number;
}

export interface SignupRequest {
  name: string;
  email: string;
  password: string;
  plan: "monthly" | "annually";
}

export interface SignupResponse {
  status: "ok";
  signup_token: string;
  stripe_url: string | null;
}

export interface ActivateRequest {
  signup_token: string;
}

export interface ActivateResponse {
  status: "activated" | "pending" | "already_active";
  message: string;
}

export interface SessionResponse {
  username: string;
  email: string;
  tier: Tier;
  brief_credits: number;
  extra_seats: number;
  is_admin: boolean;
}

// ── Tiers ─────────────────────────────────────────────

export type Tier =
  | "monthly"
  | "annually"
  | "professional"
  | "enterprise"
  | "free";

export type FeatureName =
  | "competitive_war_room"
  | "intelligence_reports"
  | "ask_moodlight"
  | "intelligence_dashboard"
  | "prediction_markets"
  | "strategic_brief"
  | "brand_watchlist"
  | "topic_watchlist"
  | "brand_focus"
  | "competitive_tracking";

// ── Core Data ─────────────────────────────────────────

export interface CombinedDataItem {
  text: string;
  created_at: string;
  source: string;
  topic: string;
  engagement: number;
  country: string;
  intensity: number;
  empathy_score: number;
  emotion_top_1: string;
  emotion_top_2: string;
  emotion_top_3: string;
  _source_table: "news_scored" | "social_scored";
}

export interface CombinedDataResponse {
  data: CombinedDataItem[];
  count: number;
}

export interface MarketData {
  timestamp: string;
  symbol: string;
  name: string;
  price: number;
  change: number;
  change_percent: string;
  volume: string;
  latest_trading_day: string;
  market_sentiment: number;
}

export interface MarketDataResponse {
  data: MarketData[];
  count: number;
}

export interface MetricSnapshot {
  scope: string;
  scope_name: string;
  metric_name: string;
  metric_value: number;
  snapshot_date: string;
}

export interface MetricDataResponse {
  data: MetricSnapshot[];
  count: number;
}

// ── Economic ──────────────────────────────────────────

export interface EconomicIndicator {
  snapshot_date: string;
  scope_name: string;
  metric_name: string;
  metric_value: number;
  sample_size: number;
}

export interface EconomicDataResponse {
  data: EconomicIndicator[];
  count: number;
}

export interface CommodityPrice {
  snapshot_date: string;
  scope_name: string;
  metric_name: string;
  metric_value: number;
  sample_size: number;
}

export interface CommodityDataResponse {
  data: CommodityPrice[];
  count: number;
}

export interface BrandStockData {
  ticker: string;
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface BrandStockResponse {
  data: BrandStockData[];
  count: number;
}

// ── Watchlists ────────────────────────────────────────

export interface BrandListResponse {
  brands: string[];
  count: number;
}

export interface TopicItem {
  topic_name: string;
  is_category: boolean;
  created_at: string;
}

export interface TopicListResponse {
  topics: TopicItem[];
  count: number;
}

// ── VLDS ──────────────────────────────────────────────

export interface VLDSScores {
  velocity: number;
  longevity: number;
  density: number;
  scarcity: number;
  _vlds_version: number;
}

export interface BrandVLDSResponse {
  brand: string;
  vlds: VLDSScores | null;
  reason?: string;
}

export interface TopicVLDSResponse {
  topic_longevity: MetricSnapshot[];
  topic_density: MetricSnapshot[];
  topic_scarcity: MetricSnapshot[];
}

// ── Alerts ────────────────────────────────────────────

export type AlertSeverity = "critical" | "warning" | "info" | "correlation" | "prediction";

export type AlertCategory = "brand" | "topic" | "global" | "predictive" | "competitive";

export interface Alert {
  id: number;
  timestamp: string;
  alert_type: string;
  severity: AlertSeverity;
  title: string;
  summary: string;
  investigation: string | null;
  data: string | null;
  emailed: boolean;
  cooldown_key: string;
  username: string;
  brand: string | null;
  topic: string | null;
  is_read: boolean;
}

export interface AlertListResponse {
  data: Alert[];
  count: number;
}

export type AlertFeedbackAction = "expanded" | "thumbs_up" | "thumbs_down";

// ── Competitive ───────────────────────────────────────

export interface CompetitorInfo {
  name: string;
  relationship: string;
}

export interface CompetitiveSnapshot {
  competitors: CompetitorInfo[];
  metrics: Record<string, unknown>;
}

export interface CompetitiveResponse {
  brand: string;
  snapshot: CompetitiveSnapshot | null;
  created_at: string;
}

// ── Claude-powered ────────────────────────────────────

export interface ChartExplainRequest {
  chart_type: ChartType;
  data_summary: string;
}

export interface ChartExplainResponse {
  explanation: string;
}

export interface AskRequest {
  message: string;
  username?: string;
  conversation_history: Array<{ role: string; content: string }>;
  last_search_info?: Record<string, unknown>;
}

export interface ReportRequest {
  subject: string;
  subject_type: "brand" | "topic";
  days: number;
  email_recipient?: string;
}

export interface ReportResponse {
  report: string;
  email_sent: boolean;
}

export interface StrategicBriefRequest {
  user_need: string;
  username?: string;
  email_recipient?: string;
}

export interface StrategicBriefResponse {
  brief: string;
  frameworks: string[];
  email_sent: boolean;
}

export interface PredictionMarket {
  yes_odds: number;
  no_odds: number;
  [key: string]: unknown;
}

export interface PredictionMarketsResponse {
  markets: PredictionMarket[];
  avg_market_confidence: number;
  avg_social_mood: number;
  divergence: string;
}

// ── User Preferences ──────────────────────────────────

export interface UserPreferences {
  digest_daily: boolean;
  digest_weekly: boolean;
  alert_emails: boolean;
}

export interface AlertPreference {
  enabled: boolean;
  sensitivity: "low" | "medium" | "high";
}

export interface AlertPreferencesResponse {
  preferences: Record<string, AlertPreference>;
}

export interface ReportSchedule {
  id: number;
  subject: string;
  subject_type: "brand" | "topic";
  frequency: "daily" | "weekly";
  email_recipient: string;
}

// ── Teams ─────────────────────────────────────────────

export interface TeamMember {
  username: string;
  email: string;
  role: "owner" | "member";
  joined_at: string;
}

export interface Team {
  id: number;
  team_name: string;
  owner_username: string;
  member_count: number;
  created_at: string;
}

// ── Admin ─────────────────────────────────────────────

export interface Customer {
  email: string;
  username: string;
  tier: Tier;
  brief_credits: number;
  stripe_customer_id: string | null;
  stripe_subscription_id: string | null;
  extra_seats: number;
  created_at: string;
}

export interface AdminAnalytics {
  active_users_7d: number;
  active_users_30d: number;
  feature_usage: Array<{
    event_type: string;
    total: number;
    unique_users: number;
  }>;
  user_activity: Array<{
    username: string;
    last_active: string;
    total_events: number;
    status: string;
  }>;
  adoption: {
    brand_watchlist_users: number;
    topic_watchlist_users: number;
    alert_feedback_users: number;
  };
}

// ── Pipeline Health ───────────────────────────────────

export interface PipelineStatus {
  status: string;
  row_count: number;
  last_run: string;
  age_hours: number;
  error_preview: string;
}

export interface PipelineHealthResponse {
  pipelines: Record<string, PipelineStatus>;
}

// ── Health ────────────────────────────────────────────

export interface HealthResponse {
  status: "ok" | "degraded";
  service: string;
  timestamp: string;
  database: string;
}

// ── Chart Types ───────────────────────────────────────

export type ChartType =
  | "empathy_by_topic"
  | "emotional_breakdown"
  | "empathy_distribution"
  | "topic_distribution"
  | "geographic_hotspots"
  | "mood_vs_market"
  | "trending_headlines"
  | "velocity_longevity"
  | "virality_empathy"
  | "mood_history"
  | "density"
  | "scarcity"
  | "economic_indicators"
  | "commodity_prices"
  | "market_sentiment"
  | "topic_intelligence"
  | "polymarket_divergence"
  | "brand_vlds"
  | "competitive_war_room"
  | "brand_comparison";

// ── API Error ─────────────────────────────────────────

export interface ApiError {
  detail: string;
}
