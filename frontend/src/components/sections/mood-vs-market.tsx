"use client";

import { useMemo } from "react";
import { useCombinedData, useMarkets } from "@/lib/hooks/use-api";
import { normalizeEmpathyScore } from "@/lib/utils";
import { LineChart } from "@/components/charts/line-chart";
import { MetricCard } from "@/components/charts/metric-card";
import { HelperButton } from "@/components/shared/helper-button";
import { ChartSkeleton } from "@/components/shared/loading-skeleton";
import type { DefaultSeries } from "@nivo/line";

export function MoodVsMarket() {
  const { data: combined, isLoading: loadingCombined } = useCombinedData(7);
  const { data: markets, isLoading: loadingMarkets } = useMarkets();

  const { chartData, latestMood, latestMarket, divergence, divergenceStatus } =
    useMemo(() => {
      if (!combined?.data?.length)
        return {
          chartData: [] as DefaultSeries[],
          latestMood: 0,
          latestMarket: 0,
          divergence: 0,
          divergenceStatus: "",
        };

      // Daily mood scores
      const byDate = new Map<string, number[]>();
      for (const item of combined.data) {
        const date = item.created_at.slice(0, 10);
        const list = byDate.get(date) || [];
        list.push(item.empathy_score);
        byDate.set(date, list);
      }

      const moodPoints = Array.from(byDate.entries())
        .map(([date, scores]) => ({
          x: date,
          y: normalizeEmpathyScore(
            scores.reduce((a, b) => a + b, 0) / scores.length
          ),
        }))
        .sort((a, b) => a.x.localeCompare(b.x));

      const moodLine = { id: "Social Mood", data: moodPoints };

      // Build daily market sentiment from markets data
      const marketEntries = (markets?.data ?? []).filter(
        (m) => m.symbol === "SPY"
      );

      // Map SPY change_percent to 0-100 scale: 50 + changePct * 5
      const spy = marketEntries.length > 0
        ? marketEntries.reduce((a, b) => (a.timestamp > b.timestamp ? a : b))
        : undefined;

      const marketValue = spy
        ? Math.round(50 + (parseFloat(spy.change_percent) || 0) * 5)
        : 50;

      // Create market line aligned to same dates as mood
      const marketLine = {
        id: "Market Index",
        data: moodPoints.map((p) => ({ x: p.x, y: marketValue })),
      };

      const series: DefaultSeries[] = [moodLine, marketLine];

      // Compute latest values and divergence
      const latestMood = moodPoints[moodPoints.length - 1]?.y ?? 0;
      const latestMarket = marketValue;
      const divergence = Math.abs(latestMood - latestMarket);
      let divergenceStatus = "";
      if (divergence > 20) divergenceStatus = "High Divergence";
      else if (divergence > 10) divergenceStatus = "Moderate Divergence";
      else divergenceStatus = "Aligned";

      return { chartData: series, latestMood, latestMarket, divergence, divergenceStatus };
    }, [combined, markets]);

  if (loadingCombined || loadingMarkets) return <ChartSkeleton />;

  const dataSummary = chartData
    .map((s) => `${s.id}: ${s.data.map((p) => `${p.x}=${p.y}`).join(", ")}`)
    .join("\n");

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-1 flex items-center gap-2">
        <p className="text-sm font-medium">Mood vs Market</p>
        <HelperButton chartType="mood_vs_market" dataSummary={dataSummary} />
      </div>
      <p className="mb-2 text-xs text-muted-foreground">
        When mood and markets diverge, that&rsquo;s your signal&mdash;opportunity or risk is coming.
      </p>
      {chartData.length > 0 && chartData[0].data.length > 0 ? (
        <>
          <LineChart data={chartData} height={300} colors={["#1f77b4", "#2E7D32"]} />
          <div className="mt-3 grid grid-cols-3 gap-3">
            <MetricCard
              label="Social Mood"
              value={Math.round(latestMood)}
              sublabel="/100"
            />
            <MetricCard
              label="Market Index"
              value={Math.round(latestMarket)}
              sublabel="/100"
            />
            <MetricCard
              label="Divergence"
              value={`${Math.round(divergence)} pts`}
              sublabel={
                divergenceStatus === "High Divergence"
                  ? "\u26A0\uFE0F " + divergenceStatus
                  : divergenceStatus === "Moderate Divergence"
                  ? "\u26A1 " + divergenceStatus
                  : "\u2705 " + divergenceStatus
              }
            />
          </div>
        </>
      ) : (
        <p className="py-4 text-center text-sm text-muted-foreground">
          Not enough data for comparison.
        </p>
      )}
    </div>
  );
}
