"use client";

import { useState, useMemo } from "react";
import { useSignalLog } from "@/lib/hooks/use-api";
import { MetricCard } from "@/components/charts/metric-card";
import { BarChart } from "@/components/charts/bar-chart";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  MetricSkeleton,
  ChartSkeleton,
  CardListSkeleton,
} from "@/components/shared/loading-skeleton";
import {
  SIGNAL_DIRECTION,
  SIGNAL_TYPE_LABELS,
  type SignalDirection,
} from "@/lib/constants";
import type { SignalLogEntry } from "@/lib/types";

// ── Helpers ──────────────────────────────────────────

function getDirection(alertType: string): SignalDirection {
  return SIGNAL_DIRECTION[alertType] ?? "volatility";
}

function isHit(entry: SignalLogEntry): boolean | null {
  if (entry.spy_change_1d == null) return null;
  const dir = getDirection(entry.alert_type);
  if (dir === "bullish") return entry.spy_change_1d > 0;
  if (dir === "bearish") return entry.spy_change_1d < 0;
  return Math.abs(entry.spy_change_1d) > 0.5;
}

function isHitHorizon(
  entry: SignalLogEntry,
  horizon: "1d" | "3d" | "5d"
): boolean | null {
  const change =
    horizon === "1d"
      ? entry.spy_change_1d
      : horizon === "3d"
        ? entry.spy_change_3d
        : entry.spy_change_5d;
  if (change == null) return null;
  const dir = getDirection(entry.alert_type);
  if (dir === "bullish") return change > 0;
  if (dir === "bearish") return change < 0;
  return Math.abs(change) > 0.5;
}

function hitRate(entries: SignalLogEntry[], horizon: "1d" | "3d" | "5d") {
  const resolved = entries.filter((e) => isHitHorizon(e, horizon) !== null);
  if (resolved.length === 0) return null;
  const hits = resolved.filter((e) => isHitHorizon(e, horizon) === true).length;
  return { rate: hits / resolved.length, resolved: resolved.length };
}

function formatPct(n: number): string {
  return `${(n * 100).toFixed(0)}%`;
}

function formatChange(n: number | null): string {
  if (n == null) return "--";
  const sign = n >= 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

function directionIcon(dir: SignalDirection): string {
  if (dir === "bullish") return "\u2191";
  if (dir === "bearish") return "\u2193";
  return "\u2194";
}

function directionColor(dir: SignalDirection): string {
  if (dir === "bullish") return "text-green-400";
  if (dir === "bearish") return "text-red-400";
  return "text-yellow-400";
}

function typeLabel(alertType: string): string {
  return SIGNAL_TYPE_LABELS[alertType] ?? alertType.replace(/_/g, " ");
}

// ── Filter types ─────────────────────────────────────

type FilterTab = "all" | "bullish" | "bearish" | "pending";
const FILTER_TABS: FilterTab[] = ["all", "bullish", "bearish", "pending"];
const PAGE_SIZE = 10;

// ── Component ────────────────────────────────────────

export function SignalTrackRecord() {
  const { data, isLoading } = useSignalLog(90);
  const [filter, setFilter] = useState<FilterTab>("all");
  const [showCount, setShowCount] = useState(PAGE_SIZE);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const entries = useMemo(() => data?.data ?? [], [data]);

  // Resolved = has 1d SPY outcome
  const resolved = useMemo(
    () => entries.filter((e) => e.spy_change_1d != null),
    [entries]
  );

  // ── Zone A: Summary metrics ────────────────────────

  const summaryMetrics = useMemo(() => {
    const hr1d = hitRate(entries, "1d");
    const avgReturn =
      resolved.length > 0
        ? resolved.reduce((s, e) => s + (e.spy_change_1d ?? 0), 0) /
          resolved.length
        : null;

    // Best type: highest hit rate with 2+ resolved signals
    const byType: Record<string, SignalLogEntry[]> = {};
    for (const e of entries) {
      (byType[e.alert_type] ??= []).push(e);
    }
    let bestType = "";
    let bestRate = 0;
    let bestCount = 0;
    for (const [type, group] of Object.entries(byType)) {
      const hr = hitRate(group, "1d");
      if (hr && hr.resolved >= 2 && hr.rate > bestRate) {
        bestRate = hr.rate;
        bestType = type;
        bestCount = hr.resolved;
      }
    }

    return { hr1d, avgReturn, bestType, bestRate, bestCount };
  }, [entries, resolved]);

  // ── Zone B: By-type performance ────────────────────

  const typePerformance = useMemo(() => {
    const byType: Record<string, SignalLogEntry[]> = {};
    for (const e of entries) {
      (byType[e.alert_type] ??= []).push(e);
    }

    const rows: {
      type: string;
      label: string;
      signals: number;
      hr1d: number | null;
      hr3d: number | null;
      hr5d: number | null;
      avgReturn: number | null;
      resolved1d: number;
    }[] = [];

    for (const [type, group] of Object.entries(byType)) {
      const hr1d = hitRate(group, "1d");
      const hr3d = hitRate(group, "3d");
      const hr5d = hitRate(group, "5d");
      const res1d = group.filter((e) => e.spy_change_1d != null);
      const avg =
        res1d.length > 0
          ? res1d.reduce((s, e) => s + (e.spy_change_1d ?? 0), 0) /
            res1d.length
          : null;

      if (hr1d && hr1d.resolved >= 2) {
        rows.push({
          type,
          label: typeLabel(type),
          signals: group.length,
          hr1d: hr1d.rate,
          hr3d: hr3d?.rate ?? null,
          hr5d: hr5d?.rate ?? null,
          avgReturn: avg,
          resolved1d: hr1d.resolved,
        });
      }
    }

    rows.sort((a, b) => (b.hr1d ?? 0) - (a.hr1d ?? 0));
    return rows;
  }, [entries]);

  // Chart data for bar chart
  const chartData = useMemo(
    () =>
      typePerformance.map((r) => ({
        type: r.label,
        "1d Hit Rate": Math.round((r.hr1d ?? 0) * 100),
      })),
    [typePerformance]
  );

  // ── Zone C: Filtered card list ─────────────────────

  const filteredEntries = useMemo(() => {
    if (filter === "all") return entries;
    if (filter === "pending")
      return entries.filter((e) => e.spy_change_1d == null);
    return entries.filter((e) => getDirection(e.alert_type) === filter);
  }, [entries, filter]);

  const visibleEntries = filteredEntries.slice(0, showCount);
  const hasMore = filteredEntries.length > showCount;

  // ── Loading state ──────────────────────────────────

  if (isLoading) {
    return (
      <div>
        <h2 className="mb-1 text-lg font-semibold">Signal Track Record</h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <MetricSkeleton key={i} />
          ))}
        </div>
        <div className="mt-4">
          <ChartSkeleton />
        </div>
        <div className="mt-4">
          <CardListSkeleton count={3} />
        </div>
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <div>
        <h2 className="mb-1 text-lg font-semibold">Signal Track Record</h2>
        <p className="py-4 text-center text-sm text-muted-foreground">
          No prediction signals logged yet. Signals will appear as the pipeline
          generates predictive alerts.
        </p>
      </div>
    );
  }

  const { hr1d, avgReturn, bestType, bestRate, bestCount } = summaryMetrics;

  return (
    <div>
      <h2 className="mb-1 text-lg font-semibold">Signal Track Record</h2>
      <p className="mb-3 text-xs text-muted-foreground">
        How Moodlight&apos;s AI predictions performed against real market
        outcomes.
      </p>

      {/* Small sample disclaimer */}
      {resolved.length < 30 && resolved.length > 0 && (
        <div className="mb-3 rounded-md border border-blue-500/30 bg-blue-500/10 px-3 py-2 text-xs text-blue-300">
          Track record based on {resolved.length} signal
          {resolved.length !== 1 ? "s" : ""}. Statistical significance improves
          as more data accumulates.
        </div>
      )}

      {/* Zone A: Summary Metrics */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <MetricCard
          label="Total Signals"
          value={entries.length}
          sublabel={`${resolved.length} with outcomes`}
        />
        <MetricCard
          label="1d Hit Rate"
          value={hr1d ? formatPct(hr1d.rate) : "--"}
          sublabel={hr1d ? `of ${hr1d.resolved} resolved` : "no data"}
          delta={
            hr1d
              ? hr1d.rate >= 0.55
                ? "Above baseline"
                : hr1d.rate < 0.45
                  ? "Below baseline"
                  : "Near baseline"
              : undefined
          }
          deltaColor={
            hr1d
              ? hr1d.rate >= 0.55
                ? "green"
                : hr1d.rate < 0.45
                  ? "red"
                  : "neutral"
              : "neutral"
          }
        />
        <MetricCard
          label="Avg 1d SPY Move"
          value={avgReturn != null ? formatChange(avgReturn) : "--"}
          sublabel="after signal"
          deltaColor={
            avgReturn != null
              ? avgReturn > 0
                ? "green"
                : avgReturn < 0
                  ? "red"
                  : "neutral"
              : "neutral"
          }
        />
        <MetricCard
          label="Best Type"
          value={bestType ? typeLabel(bestType) : "--"}
          sublabel={
            bestType
              ? `${formatPct(bestRate)} (${bestCount} signals)`
              : "no data"
          }
        />
      </div>

      {/* Zone B: Performance by Signal Type */}
      {typePerformance.length > 0 && (
        <div className="mt-4">
          <h3 className="mb-2 text-sm font-semibold">
            Performance by Signal Type
          </h3>
          <BarChart
            data={chartData}
            keys={["1d Hit Rate"]}
            indexBy="type"
            layout="horizontal"
            height={Math.min(600, Math.max(200, typePerformance.length * 36))}
            enableLabel
            colors={({ data: d }) => {
              const val = (d?.["1d Hit Rate"] as number) ?? 0;
              if (val >= 60) return "#21C354";
              if (val >= 50) return "#FACA15";
              return "#FF4B4B";
            }}
          />

          {/* Stats table */}
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th className="pb-1.5 pr-3 font-medium">Type</th>
                  <th className="pb-1.5 pr-3 font-medium text-right">
                    Signals
                  </th>
                  <th className="pb-1.5 pr-3 font-medium text-right">
                    1d Hit
                  </th>
                  <th className="pb-1.5 pr-3 font-medium text-right">
                    3d Hit
                  </th>
                  <th className="pb-1.5 pr-3 font-medium text-right">
                    5d Hit
                  </th>
                  <th className="pb-1.5 font-medium text-right">Avg Return</th>
                </tr>
              </thead>
              <tbody>
                {typePerformance.map((row) => (
                  <tr key={row.type} className="border-b border-border/50">
                    <td className="py-1.5 pr-3 font-medium">{row.label}</td>
                    <td className="py-1.5 pr-3 text-right text-muted-foreground">
                      {row.signals}
                    </td>
                    <td
                      className={`py-1.5 pr-3 text-right font-medium ${
                        row.hr1d != null && row.hr1d >= 0.6
                          ? "text-green-400"
                          : row.hr1d != null && row.hr1d < 0.5
                            ? "text-red-400"
                            : ""
                      }`}
                    >
                      {row.hr1d != null ? formatPct(row.hr1d) : "--"}
                    </td>
                    <td className="py-1.5 pr-3 text-right text-muted-foreground">
                      {row.hr3d != null ? formatPct(row.hr3d) : "--"}
                    </td>
                    <td className="py-1.5 pr-3 text-right text-muted-foreground">
                      {row.hr5d != null ? formatPct(row.hr5d) : "--"}
                    </td>
                    <td
                      className={`py-1.5 text-right ${
                        row.avgReturn != null && row.avgReturn > 0
                          ? "text-green-400"
                          : row.avgReturn != null && row.avgReturn < 0
                            ? "text-red-400"
                            : "text-muted-foreground"
                      }`}
                    >
                      {formatChange(row.avgReturn)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Zone C: Individual Signals */}
      <div className="mt-4">
        <h3 className="mb-2 text-sm font-semibold">Individual Signals</h3>

        {/* Filter tabs */}
        <div className="mb-3 flex flex-wrap gap-1.5">
          {FILTER_TABS.map((tab) => {
            const count =
              tab === "all"
                ? entries.length
                : tab === "pending"
                  ? entries.filter((e) => e.spy_change_1d == null).length
                  : entries.filter(
                      (e) => getDirection(e.alert_type) === tab
                    ).length;
            return (
              <button
                key={tab}
                onClick={() => {
                  setFilter(tab);
                  setShowCount(PAGE_SIZE);
                }}
                className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                  filter === tab
                    ? "bg-primary/20 text-primary"
                    : "text-muted-foreground hover:bg-muted"
                }`}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)} ({count})
              </button>
            );
          })}
        </div>

        {/* Signal cards */}
        <div className="space-y-2">
          {visibleEntries.length === 0 ? (
            <p className="py-4 text-center text-sm text-muted-foreground">
              No {filter === "all" ? "" : filter + " "}signals found.
            </p>
          ) : (
            visibleEntries.map((entry) => {
              const dir = getDirection(entry.alert_type);
              const pending = entry.spy_change_1d == null;
              const hit1d = isHit(entry);
              const expanded = expandedId === entry.id;

              return (
                <div
                  key={entry.id}
                  className="cursor-pointer rounded-lg border border-border bg-card p-3 transition-colors hover:bg-card/80"
                  onClick={() =>
                    setExpandedId(expanded ? null : entry.id)
                  }
                >
                  {/* Card header */}
                  <div className="flex items-start gap-2">
                    <span
                      className={`mt-0.5 text-base font-bold ${
                        pending
                          ? "text-yellow-400"
                          : directionColor(dir)
                      }`}
                    >
                      {pending ? "\u23F3" : directionIcon(dir)}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium leading-tight">
                          {entry.title}
                        </span>
                      </div>
                      <div className="mt-1 flex flex-wrap items-center gap-1.5">
                        <Badge variant="secondary" className="text-[10px]">
                          {typeLabel(entry.alert_type)}
                        </Badge>
                        {entry.brand && (
                          <Badge variant="outline" className="text-[10px]">
                            {entry.brand}
                          </Badge>
                        )}
                        <span className="text-[10px] text-muted-foreground">
                          {new Date(entry.signal_date).toLocaleDateString(
                            "en-US",
                            {
                              month: "short",
                              day: "numeric",
                            }
                          )}
                        </span>
                        {!pending && (
                          <span
                            className={`text-[10px] font-medium ${
                              hit1d ? "text-green-400" : "text-red-400"
                            }`}
                          >
                            {hit1d ? "HIT" : "MISS"}
                          </span>
                        )}
                      </div>
                    </div>
                    {/* 1d result preview */}
                    {!pending && (
                      <span
                        className={`shrink-0 text-sm font-bold tabular-nums ${
                          (entry.spy_change_1d ?? 0) >= 0
                            ? "text-green-400"
                            : "text-red-400"
                        }`}
                      >
                        {formatChange(entry.spy_change_1d)}
                      </span>
                    )}
                  </div>

                  {/* Expanded detail */}
                  {expanded && (
                    <div className="mt-3 space-y-2 border-t border-border/50 pt-3">
                      <p className="text-xs text-muted-foreground">
                        {entry.summary}
                      </p>

                      {/* SPY outcomes */}
                      <div>
                        <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                          SPY Outcomes
                        </div>
                        <div className="flex gap-4 text-xs">
                          {(["1d", "3d", "5d"] as const).map((h) => {
                            const price =
                              h === "1d"
                                ? entry.spy_price_1d
                                : h === "3d"
                                  ? entry.spy_price_3d
                                  : entry.spy_price_5d;
                            const change =
                              h === "1d"
                                ? entry.spy_change_1d
                                : h === "3d"
                                  ? entry.spy_change_3d
                                  : entry.spy_change_5d;
                            return (
                              <div key={h}>
                                <span className="text-muted-foreground">
                                  {h}:{" "}
                                </span>
                                {price != null ? (
                                  <span
                                    className={`font-medium ${
                                      (change ?? 0) >= 0
                                        ? "text-green-400"
                                        : "text-red-400"
                                    }`}
                                  >
                                    ${price.toFixed(2)} (
                                    {formatChange(change)})
                                  </span>
                                ) : (
                                  <span className="text-muted-foreground">
                                    pending
                                  </span>
                                )}
                              </div>
                            );
                          })}
                        </div>
                        <div className="mt-0.5 text-[10px] text-muted-foreground">
                          SPY at signal: $
                          {entry.spy_price_at_signal?.toFixed(2) ?? "--"}
                        </div>
                      </div>

                      {/* Brand stock outcomes */}
                      {entry.brand_ticker && entry.brand_price_at_signal && (
                        <div>
                          <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                            {entry.brand_ticker} Outcomes
                          </div>
                          <div className="flex gap-4 text-xs">
                            {(["1d", "3d", "5d"] as const).map((h) => {
                              const price =
                                h === "1d"
                                  ? entry.brand_price_1d
                                  : h === "3d"
                                    ? entry.brand_price_3d
                                    : entry.brand_price_5d;
                              const change =
                                h === "1d"
                                  ? entry.brand_change_1d
                                  : h === "3d"
                                    ? entry.brand_change_3d
                                    : entry.brand_change_5d;
                              return (
                                <div key={h}>
                                  <span className="text-muted-foreground">
                                    {h}:{" "}
                                  </span>
                                  {price != null ? (
                                    <span
                                      className={`font-medium ${
                                        (change ?? 0) >= 0
                                          ? "text-green-400"
                                          : "text-red-400"
                                      }`}
                                    >
                                      ${price.toFixed(2)} (
                                      {formatChange(change)})
                                    </span>
                                  ) : (
                                    <span className="text-muted-foreground">
                                      pending
                                    </span>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                          <div className="mt-0.5 text-[10px] text-muted-foreground">
                            {entry.brand_ticker} at signal: $
                            {entry.brand_price_at_signal?.toFixed(2) ?? "--"}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Show more */}
        {hasMore && (
          <div className="mt-3 text-center">
            <Button
              variant="ghost"
              size="sm"
              className="w-full text-xs text-muted-foreground"
              onClick={() => setShowCount((c) => c + PAGE_SIZE)}
            >
              Show more ({filteredEntries.length - showCount} remaining)
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
