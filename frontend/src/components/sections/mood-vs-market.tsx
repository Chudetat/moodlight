"use client";

import { useMemo } from "react";
import { useCombinedData, useMarkets } from "@/lib/hooks/use-api";
import { normalizeEmpathyScore } from "@/lib/utils";
import { LineChart } from "@/components/charts/line-chart";
import { HelperButton } from "@/components/shared/helper-button";
import { ChartSkeleton } from "@/components/shared/loading-skeleton";
import type { DefaultSeries } from "@nivo/line";

export function MoodVsMarket() {
  const { data: combined, isLoading: loadingCombined } = useCombinedData(7);
  const { data: markets, isLoading: loadingMarkets } = useMarkets();

  const chartData = useMemo<DefaultSeries[]>(() => {
    if (!combined?.data?.length) return [];

    // Daily mood scores
    const byDate = new Map<string, number[]>();
    for (const item of combined.data) {
      const date = item.created_at.slice(0, 10);
      const list = byDate.get(date) || [];
      list.push(item.empathy_score);
      byDate.set(date, list);
    }

    const moodLine = {
      id: "Mood Score",
      data: Array.from(byDate.entries())
        .map(([date, scores]) => ({
          x: date,
          y: normalizeEmpathyScore(
            scores.reduce((a, b) => a + b, 0) / scores.length
          ),
        }))
        .sort((a, b) => a.x.localeCompare(b.x)),
    };

    // SPY as market proxy (normalize to 0-100 range for visual comparison)
    // Find the latest SPY entry by timestamp
    const spyEntries = (markets?.data ?? []).filter((m) => m.symbol === "SPY");
    const spy = spyEntries.length > 0
      ? spyEntries.reduce((a, b) => (a.timestamp > b.timestamp ? a : b))
      : undefined;
    const series: DefaultSeries[] = [moodLine];
    if (spy) {
      const changePct = parseFloat(spy.change_percent) || 0;
      const lastDate = moodLine.data[moodLine.data.length - 1]?.x;
      if (lastDate) {
        series.push({
          id: "S&P 500 (scaled)",
          data: moodLine.data.map((p) => ({
            x: p.x,
            y: Math.round(50 + changePct * 5),
          })),
        });
      }
    }

    return series;
  }, [combined, markets]);

  if (loadingCombined || loadingMarkets) return <ChartSkeleton />;

  const dataSummary = chartData
    .map((s) => `${s.id}: ${s.data.map((p) => `${p.x}=${p.y}`).join(", ")}`)
    .join("\n");

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-2 flex items-center gap-2">
        <p className="text-sm font-medium">Mood vs Market</p>
        <HelperButton chartType="mood_vs_market" dataSummary={dataSummary} />
      </div>
      {chartData.length > 0 && chartData[0].data.length > 0 ? (
        <LineChart data={chartData} height={300} colors={["#1f77b4", "#2E7D32"]} />
      ) : (
        <p className="py-4 text-center text-sm text-muted-foreground">
          Not enough data for comparison.
        </p>
      )}
    </div>
  );
}
