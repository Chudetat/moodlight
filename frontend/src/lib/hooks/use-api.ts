"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type {
  CombinedDataResponse,
  MarketDataResponse,
  EconomicDataResponse,
  CommodityDataResponse,
  BrandStockResponse,
  BrandListResponse,
  TopicListResponse,
  BrandVLDSResponse,
  TopicVLDSResponse,
  AlertListResponse,
  CompetitiveResponse,
  ChartExplainRequest,
  ChartExplainResponse,
  AlertFeedbackAction,
  PredictionMarketsResponse,
  UserPreferences,
  AlertPreferencesResponse,
  PipelineHealthResponse,
  ReportSchedule,
  Team,
  TeamMember,
  Customer,
} from "../types";

const REFETCH_INTERVAL = 5 * 60_000; // 5 minutes

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/proxy${path}`, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || res.statusText);
  }
  return res.json();
}

// ── Core Data ─────────────────────────────────────────

export function useCombinedData(days = 7) {
  return useQuery<CombinedDataResponse>({
    queryKey: ["combined", days],
    queryFn: () => apiFetch(`/api/data/combined?days=${days}`),
    refetchInterval: REFETCH_INTERVAL,
  });
}

export function useMarkets(days = 7) {
  return useQuery<MarketDataResponse>({
    queryKey: ["markets", days],
    queryFn: () => apiFetch(`/api/data/markets?days=${days}`),
    refetchInterval: REFETCH_INTERVAL,
  });
}

export function useEconomicData(days = 730) {
  return useQuery<EconomicDataResponse>({
    queryKey: ["economic", days],
    queryFn: () => apiFetch(`/api/economic?days=${days}`),
    refetchInterval: REFETCH_INTERVAL,
  });
}

export function useCommodities(days = 90) {
  return useQuery<CommodityDataResponse>({
    queryKey: ["commodities", days],
    queryFn: () => apiFetch(`/api/commodities?days=${days}`),
    refetchInterval: REFETCH_INTERVAL,
  });
}

export function useBrandStocks(ticker: string, days = 2) {
  return useQuery<BrandStockResponse>({
    queryKey: ["brand-stocks", ticker, days],
    queryFn: () => apiFetch(`/api/brand-stocks/${ticker}?days=${days}`),
    enabled: !!ticker,
    refetchInterval: REFETCH_INTERVAL,
  });
}

// ── Watchlists ────────────────────────────────────────

export function useBrands(username: string) {
  return useQuery<BrandListResponse>({
    queryKey: ["brands", username],
    queryFn: () => apiFetch(`/api/brands/${username}`),
    enabled: !!username,
  });
}

export function useTopics(username: string) {
  return useQuery<TopicListResponse>({
    queryKey: ["topics", username],
    queryFn: () => apiFetch(`/api/topics/${username}`),
    enabled: !!username,
  });
}

// ── VLDS ──────────────────────────────────────────────

export function useBrandVLDS(brand: string, days = 7) {
  return useQuery<BrandVLDSResponse>({
    queryKey: ["vlds-brand", brand, days],
    queryFn: () => apiFetch(`/api/vlds/brand/${encodeURIComponent(brand)}?days=${days}`),
    enabled: !!brand,
    refetchInterval: REFETCH_INTERVAL,
  });
}

export function useTopicVLDS() {
  return useQuery<TopicVLDSResponse>({
    queryKey: ["vlds-topics"],
    queryFn: () => apiFetch("/api/vlds/topics"),
    refetchInterval: REFETCH_INTERVAL,
  });
}

// ── Alerts ────────────────────────────────────────────

export function useAlerts(username: string, days = 7, severity?: string) {
  const params = new URLSearchParams({ days: String(days) });
  if (severity) params.set("severity", severity);
  return useQuery<AlertListResponse>({
    queryKey: ["alerts", username, days, severity],
    queryFn: () => apiFetch(`/api/alerts/${username}?${params}`),
    enabled: !!username,
    refetchInterval: REFETCH_INTERVAL,
  });
}

export function useMarkAlertRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (alertId: number) =>
      apiFetch(`/api/alerts/${alertId}/mark-read`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}

export function useAlertFeedback() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      alertId,
      action,
    }: {
      alertId: number;
      action: AlertFeedbackAction;
    }) =>
      apiFetch(`/api/alerts/${alertId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}

// ── Competitive ───────────────────────────────────────

export function useCompetitive(brand: string) {
  return useQuery<CompetitiveResponse>({
    queryKey: ["competitive", brand],
    queryFn: () =>
      apiFetch(`/api/competitive/${encodeURIComponent(brand)}`),
    enabled: !!brand,
  });
}

// ── Claude-powered ────────────────────────────────────

export function useChartExplain() {
  return useMutation<ChartExplainResponse, Error, ChartExplainRequest>({
    mutationFn: (req) =>
      apiFetch("/api/chart/explain", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
      }),
  });
}

// ── Prediction Markets ────────────────────────────────

export function usePredictionMarkets() {
  return useQuery<PredictionMarketsResponse>({
    queryKey: ["prediction-markets"],
    queryFn: () => apiFetch("/api/prediction-markets"),
    refetchInterval: REFETCH_INTERVAL,
  });
}

// ── User Preferences ──────────────────────────────────

export function useUserPreferences() {
  return useQuery<UserPreferences>({
    queryKey: ["user-preferences"],
    queryFn: () => apiFetch("/api/user/preferences"),
  });
}

export function useAlertPreferences() {
  return useQuery<AlertPreferencesResponse>({
    queryKey: ["alert-preferences"],
    queryFn: () => apiFetch("/api/user/alert-preferences"),
  });
}

// ── Watchlist Mutations ──────────────────────────────

export function useAddBrand() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (brandName: string) =>
      apiFetch("/api/watchlist/brands", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ brand_name: brandName }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["brands"] }),
  });
}

export function useRemoveBrand() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (brandName: string) =>
      apiFetch(`/api/watchlist/brands/${encodeURIComponent(brandName)}`, {
        method: "DELETE",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["brands"] }),
  });
}

export function useAddTopic() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { topic_name: string; is_category: boolean }) =>
      apiFetch("/api/watchlist/topics", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["topics"] }),
  });
}

export function useRemoveTopic() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (topicName: string) =>
      apiFetch(`/api/watchlist/topics/${encodeURIComponent(topicName)}`, {
        method: "DELETE",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["topics"] }),
  });
}

// ── Alert Mutations ──────────────────────────────────

export function useMarkAllAlertsRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch("/api/alerts/mark-all-read", { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });
}

// ── Preference Mutations ─────────────────────────────

export function useUpdateUserPreferences() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<UserPreferences>) =>
      apiFetch("/api/user/preferences", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["user-preferences"] }),
  });
}

export function useUpdateAlertPreferences() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      alert_type?: string;
      enabled?: boolean;
      sensitivity?: string;
    }) =>
      apiFetch("/api/user/alert-preferences", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alert-preferences"] }),
  });
}

// ── Report Schedules ─────────────────────────────────

export function useReportSchedules() {
  return useQuery<{ schedules: ReportSchedule[]; count: number }>({
    queryKey: ["reportSchedules"],
    queryFn: () => apiFetch("/api/user/report-schedules"),
  });
}

export function useCreateReportSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      subject: string;
      subject_type: string;
      frequency: string;
      days_lookback?: number;
    }) =>
      apiFetch("/api/user/report-schedules", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reportSchedules"] }),
  });
}

export function useToggleReportSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) =>
      apiFetch(`/api/user/report-schedules/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reportSchedules"] }),
  });
}

export function useDeleteReportSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/api/user/report-schedules/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reportSchedules"] }),
  });
}

// ── Teams ────────────────────────────────────────────

export function useUserTeam() {
  return useQuery<{ team: (Team & { role: string }) | null }>({
    queryKey: ["userTeam"],
    queryFn: () => apiFetch("/api/user/team"),
  });
}

export function useTeamMembers(teamId: number | undefined) {
  return useQuery<{ members: TeamMember[]; count: number }>({
    queryKey: ["teamMembers", teamId],
    queryFn: () => apiFetch(`/api/teams/${teamId}/members`),
    enabled: !!teamId,
  });
}

export function useInviteTeamMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      teamId,
      email,
      name,
    }: {
      teamId: number;
      email: string;
      name: string;
    }) =>
      apiFetch(`/api/teams/${teamId}/members`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, name }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["teamMembers"] }),
  });
}

export function useRemoveTeamMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      teamId,
      username,
    }: {
      teamId: number;
      username: string;
    }) =>
      apiFetch(`/api/teams/${teamId}/members/${username}`, {
        method: "DELETE",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["teamMembers"] }),
  });
}

export function useTeamWatchlists(teamId: number | undefined) {
  return useQuery<{
    brands: string[];
    topics: { topic_name: string; is_category: boolean }[];
  }>({
    queryKey: ["teamWatchlists", teamId],
    queryFn: () => apiFetch(`/api/teams/${teamId}/watchlists`),
    enabled: !!teamId,
  });
}

export function useCreateUserTeam() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { team_name: string; owner_username: string }) =>
      apiFetch<{ status: string; team_id: number; team_name: string }>(
        "/api/admin/teams",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        }
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["userTeam"] }),
  });
}

// ── Claude-powered Generators ────────────────────────

export function useGenerateReport() {
  return useMutation({
    mutationFn: (data: {
      subject: string;
      days?: number;
      username?: string;
      send_email?: boolean;
    }) =>
      apiFetch<{ report: string; email_sent: boolean }>("/api/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
  });
}

export function useGenerateStrategicBrief() {
  return useMutation({
    mutationFn: (data: {
      user_need: string;
      username?: string;
      email_recipient?: string;
    }) =>
      apiFetch<{ brief: string; frameworks: string[]; email_sent: boolean }>(
        "/api/strategic-brief",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        }
      ),
  });
}

export function useAskMoodlight() {
  return useMutation({
    mutationFn: (data: {
      message: string;
      username?: string;
      conversation_history?: { role: string; content: string }[];
      last_search_info?: Record<string, unknown> | null;
    }) =>
      apiFetch<{ response: string; search_info?: Record<string, unknown> }>(
        "/api/ask",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        }
      ),
  });
}

// ── Support ──────────────────────────────────────────

export function useSendSupport() {
  return useMutation({
    mutationFn: (data: { message: string }) =>
      apiFetch<{ status: string }>("/api/support", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
  });
}

export function useLogEvent() {
  return useMutation({
    mutationFn: (data: { event_type: string; event_data?: string }) =>
      apiFetch("/api/user/events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
  });
}

// ── Admin ────────────────────────────────────────────

export function useAdminCustomers() {
  return useQuery<{ customers: Customer[]; count: number }>({
    queryKey: ["admin", "customers"],
    queryFn: () => apiFetch("/api/admin/customers"),
  });
}

export function useAdminAnalytics() {
  return useQuery({
    queryKey: ["admin", "analytics"],
    queryFn: () => apiFetch<Record<string, unknown>>("/api/admin/analytics"),
  });
}

export function useAdminTeams() {
  return useQuery({
    queryKey: ["admin", "teams"],
    queryFn: () =>
      apiFetch<{ teams: Record<string, unknown>[]; count: number }>(
        "/api/admin/teams"
      ),
  });
}

export function useCreateCustomer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      email: string;
      name: string;
      tier?: string;
      initial_credits?: number;
    }) =>
      apiFetch<{
        username: string;
        email: string;
        tier: string;
        temp_password: string;
      }>("/api/admin/customers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "customers"] }),
  });
}

export function useUpdateCustomer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      username,
      ...data
    }: {
      username: string;
      tier?: string;
      extra_seats?: number;
    }) =>
      apiFetch(`/api/admin/customers/${username}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "customers"] }),
  });
}

export function useDeleteCustomer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (username: string) =>
      apiFetch(`/api/admin/customers/${username}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "customers"] }),
  });
}

export function useAddCredits() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ username, credits }: { username: string; credits: number }) =>
      apiFetch(`/api/admin/customers/${username}/credits`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ credits }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "customers"] }),
  });
}

// ── Metrics / Historical Trends ──────────────────────

export function useMetricTrends(
  scope: string,
  scopeName?: string,
  days = 90
) {
  const params = new URLSearchParams({ days: String(days) });
  if (scopeName) params.set("scope_name", scopeName);
  return useQuery<{
    data: { snapshot_date: string; metric_name: string; metric_value: number }[];
    count: number;
  }>({
    queryKey: ["metrics", scope, scopeName, days],
    queryFn: () => apiFetch(`/api/metrics/${scope}?${params}`),
    enabled: days > 7,
  });
}

// ── Pipeline Health ───────────────────────────────────

export function usePipelineHealth() {
  return useQuery<PipelineHealthResponse>({
    queryKey: ["pipeline-health"],
    queryFn: () => apiFetch("/api/pipeline-health"),
    refetchInterval: 5 * 60_000,
  });
}
