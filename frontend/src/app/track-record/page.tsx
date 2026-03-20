"use client";

import { useState, useMemo } from "react";
import Image from "next/image";
import Link from "next/link";
import { useSignalLog } from "@/lib/hooks/use-api";
import { useTopicSignals, useOpportunities } from "@/lib/hooks/use-api";
import { Badge } from "@/components/ui/badge";
import {
  SIGNAL_DIRECTION,
  SIGNAL_TYPE_LABELS,
  type SignalDirection,
} from "@/lib/constants";
import type { SignalLogEntry } from "@/lib/types";

// ── Helpers (shared logic with signal-track-record.tsx) ──

function getDirection(alertType: string): SignalDirection {
  return SIGNAL_DIRECTION[alertType] ?? "volatility";
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

function typeLabel(alertType: string): string {
  return SIGNAL_TYPE_LABELS[alertType] ?? alertType.replace(/_/g, " ");
}

function directionBadge(dir: SignalDirection) {
  if (dir === "bullish")
    return (
      <span className="inline-flex items-center rounded-full bg-green-500/15 px-2 py-0.5 text-[10px] font-medium text-green-400">
        Bullish
      </span>
    );
  if (dir === "bearish")
    return (
      <span className="inline-flex items-center rounded-full bg-red-500/15 px-2 py-0.5 text-[10px] font-medium text-red-400">
        Bearish
      </span>
    );
  return (
    <span className="inline-flex items-center rounded-full bg-yellow-500/15 px-2 py-0.5 text-[10px] font-medium text-yellow-400">
      Volatility
    </span>
  );
}

// ── Metric Card ──

function MetricBox({
  label,
  value,
  sublabel,
  color,
}: {
  label: string;
  value: string | number;
  sublabel?: string;
  color?: "green" | "red" | "neutral";
}) {
  const valueColor =
    color === "green"
      ? "text-green-400"
      : color === "red"
        ? "text-red-400"
        : "text-white";
  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-4">
      <div className="text-xs font-medium uppercase tracking-wider text-white/50">
        {label}
      </div>
      <div className={`mt-1 text-2xl font-bold ${valueColor}`}>{value}</div>
      {sublabel && (
        <div className="mt-0.5 text-xs text-white/40">{sublabel}</div>
      )}
    </div>
  );
}

// ── Main Page ──

export default function TrackRecordPage() {
  const { data: signalData, isLoading: signalsLoading } = useSignalLog(180);
  const { data: topicsData } = useTopicSignals();
  const { data: oppsData } = useOpportunities();
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const entries = useMemo(() => signalData?.data ?? [], [signalData]);
  const resolved = useMemo(
    () => entries.filter((e) => e.spy_change_1d != null),
    [entries]
  );

  // Summary metrics
  const summary = useMemo(() => {
    const hr1d = hitRate(entries, "1d");
    const avgReturn =
      resolved.length > 0
        ? resolved.reduce((s, e) => s + (e.spy_change_1d ?? 0), 0) /
          resolved.length
        : null;

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

  // Type performance table
  const typePerformance = useMemo(() => {
    const byType: Record<string, SignalLogEntry[]> = {};
    for (const e of entries) {
      (byType[e.alert_type] ??= []).push(e);
    }

    const rows: {
      type: string;
      label: string;
      direction: SignalDirection;
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
          direction: getDirection(type),
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

  // Recent signals (last 20 resolved + pending)
  const recentSignals = entries.slice(0, 20);

  const dateStr = new Date().toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  });

  if (signalsLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0a0a0a]">
        <div className="text-white/50">Loading track record...</div>
      </div>
    );
  }

  const { hr1d, avgReturn, bestType, bestRate, bestCount } = summary;

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      {/* Hero */}
      <header className="border-b border-white/10 px-6 py-12 text-center">
        <Link href="/">
          <Image
            src="/logo.png"
            alt="Moodlight"
            width={200}
            height={40}
            className="mx-auto mb-6"
            priority
          />
        </Link>
        <h1 className="text-3xl font-bold tracking-tight">
          Signal Track Record
        </h1>
        <p className="mx-auto mt-3 max-w-lg text-sm text-white/60">
          How Moodlight&apos;s AI predictions performed against real market
          outcomes. Every signal is logged, every outcome is tracked.
        </p>
        <p className="mt-2 text-xs text-white/30">{dateStr}</p>
      </header>

      <main className="mx-auto max-w-4xl px-6 py-10">
        {/* Sample size notice */}
        {resolved.length > 0 && resolved.length < 50 && (
          <div className="mb-6 rounded-lg border border-blue-500/20 bg-blue-500/5 px-4 py-3 text-xs text-blue-300">
            Track record based on {resolved.length} resolved signal
            {resolved.length !== 1 ? "s" : ""} over{" "}
            {entries.length > 0
              ? Math.ceil(
                  (Date.now() -
                    new Date(
                      entries[entries.length - 1].signal_date
                    ).getTime()) /
                    (1000 * 60 * 60 * 24)
                )
              : 0}{" "}
            days. Statistical significance improves as more data accumulates.
          </div>
        )}

        {/* Summary Metrics */}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <MetricBox
            label="Total Signals"
            value={entries.length}
            sublabel={`${resolved.length} with outcomes`}
          />
          <MetricBox
            label="1d Hit Rate"
            value={hr1d ? formatPct(hr1d.rate) : "--"}
            sublabel={hr1d ? `of ${hr1d.resolved} resolved` : "no data"}
            color={
              hr1d
                ? hr1d.rate >= 0.55
                  ? "green"
                  : hr1d.rate < 0.45
                    ? "red"
                    : "neutral"
                : "neutral"
            }
          />
          <MetricBox
            label="Avg 1d SPY Move"
            value={avgReturn != null ? formatChange(avgReturn) : "--"}
            sublabel="after signal"
            color={
              avgReturn != null
                ? avgReturn > 0
                  ? "green"
                  : avgReturn < 0
                    ? "red"
                    : "neutral"
                : "neutral"
            }
          />
          <MetricBox
            label="Best Signal Type"
            value={bestType ? typeLabel(bestType) : "--"}
            sublabel={
              bestType
                ? `${formatPct(bestRate)} hit rate (${bestCount} signals)`
                : "no data"
            }
          />
        </div>

        {/* Performance by Type */}
        {typePerformance.length > 0 && (
          <section className="mt-10">
            <h2 className="mb-4 text-lg font-semibold">
              Performance by Signal Type
            </h2>
            <div className="overflow-x-auto rounded-xl border border-white/10">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/10 bg-white/5 text-left text-xs uppercase tracking-wider text-white/50">
                    <th className="px-4 py-3 font-medium">Signal Type</th>
                    <th className="px-4 py-3 font-medium text-center">
                      Direction
                    </th>
                    <th className="px-4 py-3 font-medium text-right">
                      Signals
                    </th>
                    <th className="px-4 py-3 font-medium text-right">
                      1d Hit
                    </th>
                    <th className="px-4 py-3 font-medium text-right">
                      3d Hit
                    </th>
                    <th className="px-4 py-3 font-medium text-right">
                      5d Hit
                    </th>
                    <th className="px-4 py-3 font-medium text-right">
                      Avg Return
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {typePerformance.map((row) => (
                    <tr
                      key={row.type}
                      className="border-b border-white/5 transition-colors hover:bg-white/5"
                    >
                      <td className="px-4 py-3 font-medium">{row.label}</td>
                      <td className="px-4 py-3 text-center">
                        {directionBadge(row.direction)}
                      </td>
                      <td className="px-4 py-3 text-right text-white/50">
                        {row.signals}
                      </td>
                      <td
                        className={`px-4 py-3 text-right font-semibold ${
                          row.hr1d != null && row.hr1d >= 0.6
                            ? "text-green-400"
                            : row.hr1d != null && row.hr1d < 0.5
                              ? "text-red-400"
                              : "text-yellow-400"
                        }`}
                      >
                        {row.hr1d != null ? formatPct(row.hr1d) : "--"}
                      </td>
                      <td className="px-4 py-3 text-right text-white/50">
                        {row.hr3d != null ? formatPct(row.hr3d) : "--"}
                      </td>
                      <td className="px-4 py-3 text-right text-white/50">
                        {row.hr5d != null ? formatPct(row.hr5d) : "--"}
                      </td>
                      <td
                        className={`px-4 py-3 text-right font-medium ${
                          row.avgReturn != null && row.avgReturn > 0
                            ? "text-green-400"
                            : row.avgReturn != null && row.avgReturn < 0
                              ? "text-red-400"
                              : "text-white/50"
                        }`}
                      >
                        {formatChange(row.avgReturn)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {/* Recent Signals */}
        {recentSignals.length > 0 && (
          <section className="mt-10">
            <h2 className="mb-4 text-lg font-semibold">Recent Signals</h2>
            <div className="space-y-2">
              {recentSignals.map((entry) => {
                const dir = getDirection(entry.alert_type);
                const pending = entry.spy_change_1d == null;
                const hit1d = isHitHorizon(entry, "1d");
                const expanded = expandedId === entry.id;

                return (
                  <div
                    key={entry.id}
                    className="cursor-pointer rounded-xl border border-white/10 bg-white/5 p-4 transition-colors hover:bg-white/[0.08]"
                    onClick={() =>
                      setExpandedId(expanded ? null : entry.id)
                    }
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium leading-tight">
                          {entry.title}
                        </div>
                        <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                          <Badge
                            variant="secondary"
                            className="bg-white/10 text-[10px] text-white/70"
                          >
                            {typeLabel(entry.alert_type)}
                          </Badge>
                          {directionBadge(dir)}
                          {entry.brand && (
                            <Badge
                              variant="outline"
                              className="border-white/20 text-[10px] text-white/60"
                            >
                              {entry.brand}
                            </Badge>
                          )}
                          <span className="text-[10px] text-white/30">
                            {new Date(entry.signal_date).toLocaleDateString(
                              "en-US",
                              { month: "short", day: "numeric", year: "numeric" }
                            )}
                          </span>
                          {!pending && (
                            <span
                              className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                                hit1d
                                  ? "bg-green-500/15 text-green-400"
                                  : "bg-red-500/15 text-red-400"
                              }`}
                            >
                              {hit1d ? "HIT" : "MISS"}
                            </span>
                          )}
                          {pending && (
                            <span className="rounded-full bg-yellow-500/15 px-2 py-0.5 text-[10px] font-medium text-yellow-400">
                              PENDING
                            </span>
                          )}
                        </div>
                      </div>
                      {!pending && (
                        <span
                          className={`shrink-0 text-lg font-bold tabular-nums ${
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
                      <div className="mt-4 space-y-3 border-t border-white/10 pt-4">
                        <p className="text-xs text-white/50">{entry.summary}</p>

                        <div>
                          <div className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-white/30">
                            SPY Outcomes
                          </div>
                          <div className="flex gap-6 text-xs">
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
                                  <span className="text-white/40">{h}: </span>
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
                                    <span className="text-white/30">
                                      pending
                                    </span>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                          <div className="mt-1 text-[10px] text-white/30">
                            SPY at signal: $
                            {entry.spy_price_at_signal?.toFixed(2) ?? "--"}
                          </div>
                        </div>

                        {entry.brand_ticker &&
                          entry.brand_price_at_signal && (
                            <div>
                              <div className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-white/30">
                                {entry.brand_ticker} Outcomes
                              </div>
                              <div className="flex gap-6 text-xs">
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
                                      <span className="text-white/40">
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
                                        <span className="text-white/30">
                                          pending
                                        </span>
                                      )}
                                    </div>
                                  );
                                })}
                              </div>
                              <div className="mt-1 text-[10px] text-white/30">
                                {entry.brand_ticker} at signal: $
                                {entry.brand_price_at_signal?.toFixed(2) ??
                                  "--"}
                              </div>
                            </div>
                          )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* Cultural Landscape */}
        {oppsData && (
          <section className="mt-10">
            <h2 className="mb-4 text-lg font-semibold">
              Current Cultural Landscape
            </h2>
            <div className="grid gap-4 md:grid-cols-2">
              {/* Opportunities */}
              {oppsData.opportunities.length > 0 && (
                <div className="rounded-xl border border-green-500/20 bg-green-500/5 p-4">
                  <h3 className="mb-3 text-sm font-semibold text-green-400">
                    Opportunity Zones
                  </h3>
                  <p className="mb-3 text-[10px] text-white/40">
                    High scarcity + low density = gaps nobody is filling
                  </p>
                  <div className="space-y-2">
                    {oppsData.opportunities.slice(0, 5).map((t) => (
                      <div
                        key={t.topic}
                        className="flex items-center justify-between text-xs"
                      >
                        <span className="font-medium">{t.topic}</span>
                        <div className="flex gap-2 text-white/40">
                          <span>
                            scarcity:{" "}
                            <span className="text-green-400">
                              {t.scarcity?.toFixed(2)}
                            </span>
                          </span>
                          <span>
                            density:{" "}
                            <span className="text-white/60">
                              {t.density?.toFixed(2)}
                            </span>
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Saturated */}
              {oppsData.saturated.length > 0 && (
                <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4">
                  <h3 className="mb-3 text-sm font-semibold text-red-400">
                    Saturated Topics
                  </h3>
                  <p className="mb-3 text-[10px] text-white/40">
                    High density = everyone is already here
                  </p>
                  <div className="space-y-2">
                    {oppsData.saturated.slice(0, 5).map((t) => (
                      <div
                        key={t.topic}
                        className="flex items-center justify-between text-xs"
                      >
                        <span className="font-medium">{t.topic}</span>
                        <div className="flex gap-2 text-white/40">
                          <span>
                            density:{" "}
                            <span className="text-red-400">
                              {t.density?.toFixed(2)}
                            </span>
                          </span>
                          <span>
                            velocity:{" "}
                            <span className="text-white/60">
                              {t.velocity?.toFixed(2)}
                            </span>
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Rising Edges */}
            {oppsData.rising_edges.length > 0 && (
              <div className="mt-4 rounded-xl border border-yellow-500/20 bg-yellow-500/5 p-4">
                <h3 className="mb-3 text-sm font-semibold text-yellow-400">
                  Rising Edges
                </h3>
                <p className="mb-3 text-[10px] text-white/40">
                  High velocity + low density = emerging, not yet crowded
                </p>
                <div className="grid gap-2 md:grid-cols-2">
                  {oppsData.rising_edges.slice(0, 6).map((t) => (
                    <div
                      key={t.topic}
                      className="flex items-center justify-between text-xs"
                    >
                      <span className="font-medium">{t.topic}</span>
                      <div className="flex gap-2 text-white/40">
                        <span>
                          velocity:{" "}
                          <span className="text-yellow-400">
                            {t.velocity?.toFixed(2)}
                          </span>
                        </span>
                        <span>
                          density:{" "}
                          <span className="text-white/60">
                            {t.density?.toFixed(2)}
                          </span>
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </section>
        )}

        {/* Topic Signals */}
        {topicsData && topicsData.topics.length > 0 && (
          <section className="mt-10">
            <h2 className="mb-4 text-lg font-semibold">
              VLDS Topic Intelligence
            </h2>
            <div className="overflow-x-auto rounded-xl border border-white/10">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-white/10 bg-white/5 text-left uppercase tracking-wider text-white/50">
                    <th className="px-3 py-2.5 font-medium">Topic</th>
                    <th className="px-3 py-2.5 font-medium text-right">
                      Velocity
                    </th>
                    <th className="px-3 py-2.5 font-medium text-right">
                      Longevity
                    </th>
                    <th className="px-3 py-2.5 font-medium text-right">
                      Density
                    </th>
                    <th className="px-3 py-2.5 font-medium text-right">
                      Scarcity
                    </th>
                    <th className="px-3 py-2.5 font-medium text-right">
                      Opp Score
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {topicsData.topics.slice(0, 12).map((t) => (
                    <tr
                      key={t.topic}
                      className="border-b border-white/5 transition-colors hover:bg-white/5"
                    >
                      <td className="px-3 py-2 font-medium">{t.topic}</td>
                      <td className="px-3 py-2 text-right">
                        <span className="text-white/70">
                          {t.velocity?.toFixed(2) ?? "--"}
                        </span>
                        <span className="ml-1 text-[10px] text-white/30">
                          {t.velocity_label}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-right text-white/50">
                        {t.longevity?.toFixed(2) ?? "--"}
                      </td>
                      <td
                        className={`px-3 py-2 text-right ${
                          (t.density ?? 0) > 0.7
                            ? "text-red-400"
                            : (t.density ?? 0) < 0.3
                              ? "text-green-400"
                              : "text-white/50"
                        }`}
                      >
                        {t.density?.toFixed(2) ?? "--"}
                      </td>
                      <td
                        className={`px-3 py-2 text-right ${
                          (t.scarcity ?? 0) > 0.5
                            ? "text-green-400"
                            : "text-white/50"
                        }`}
                      >
                        {t.scarcity?.toFixed(2) ?? "--"}
                      </td>
                      <td className="px-3 py-2 text-right font-semibold text-orange-400">
                        {t.opportunity_score?.toFixed(2) ?? "--"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-white/10 px-6 py-8 text-center">
        <p className="text-xs text-white/30">
          Powered by{" "}
          <Link
            href="https://moodlight.app"
            className="text-orange-400 hover:text-orange-300"
          >
            Moodlight
          </Link>{" "}
          &mdash; Real-time cultural & competitive intelligence
        </p>
        <p className="mt-1 text-[10px] text-white/20">
          Data updates every 5 minutes. Signal outcomes tracked at 1-day,
          3-day, and 5-day horizons.
        </p>
      </footer>
    </div>
  );
}
