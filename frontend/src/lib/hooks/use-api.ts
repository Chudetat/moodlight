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
} from "../types";

const REFETCH_INTERVAL = 60_000; // 1 minute

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

export function useMarkets() {
  return useQuery<MarketDataResponse>({
    queryKey: ["markets"],
    queryFn: () => apiFetch("/api/data/markets"),
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

export function useCommodities(days = 7) {
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

// ── Pipeline Health ───────────────────────────────────

export function usePipelineHealth() {
  return useQuery<PipelineHealthResponse>({
    queryKey: ["pipeline-health"],
    queryFn: () => apiFetch("/api/pipeline-health"),
    refetchInterval: 5 * 60_000,
  });
}
