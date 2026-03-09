"use client";

import { useMemo } from "react";
import { useCombinedData, useMarkets } from "@/lib/hooks/use-api";
import { normalizeEmpathyScore } from "@/lib/utils";
import { LineChart } from "@/components/charts/line-chart";
import { MetricCard } from "@/components/charts/metric-card";
import { HelperButton } from "@/components/shared/helper-button";
import { ChartSkeleton } from "@/components/shared/loading-skeleton";
import type { DefaultSeries } from "@/components/charts/line-chart";

const LOOKBACK_DAYS = 30;

export function MoodVsMarket() {
  const { data: combined, isLoading: loadingCombined } = useCombinedData(LOOKBACK_DAYS);
  const { data: markets, isLoading: loadingMarkets } = useMarkets(LOOKBACK_DAYS);

  const { chartData, latestMood, latestMarket, divergence, divergenceStatus } =
    useMemo(() => {
      const empty = {
        chartData: [] as DefaultSeries[],
        latestMood: 0,
        latestMarket: 0,
        divergence: 0,
        divergenceStatus: "",
      };
      if (!combined?.data?.length) return empty;

      // Daily mood scores (grouped by date)
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

      // Build daily market sentiment from market_sentiment field (matches Streamlit)
      const marketRows = markets?.data ?? [];
      const marketByDate = new Map<string, number[]>();
      for (const row of marketRows) {
        if (row.latest_trading_day && row.market_sentiment != null) {
          const date = row.latest_trading_day.slice(0, 10);
          const list = marketByDate.get(date) || [];
          list.push(row.market_sentiment);
          marketByDate.set(date, list);
        }
      }

      const marketPoints = Array.from(marketByDate.entries())
        .map(([date, sentiments]) => ({
          x: date,
          y: Math.round(
            (sentiments.reduce((a, b) => a + b, 0) / sentiments.length) * 100
          ),
        }))
        .sort((a, b) => a.x.localeCompare(b.x));

      // Merge all dates from both lines, fill gaps with nearest value
      const allDatesSet = new Set<string>();
      for (const p of moodPoints) allDatesSet.add(p.x);
      for (const p of marketPoints) allDatesSet.add(p.x);
      const allDates = Array.from(allDatesSet).sort();

      const moodMap = new Map(moodPoints.map((p) => [p.x, p.y]));
      const marketMap = new Map(marketPoints.map((p) => [p.x, p.y]));

      // Forward-fill then back-fill gaps
      const fillGaps = (map: Map<string, number>, dates: string[]) => {
        const filled = new Map<string, number>();
        let lastVal: number | null = null;
        for (const d of dates) {
          if (map.has(d)) {
            lastVal = map.get(d)!;
          }
          if (lastVal !== null) filled.set(d, lastVal);
        }
        // Back-fill any leading gaps
        let firstVal: number | null = null;
        for (const d of dates) {
          if (filled.has(d)) {
            firstVal = filled.get(d)!;
            break;
          }
        }
        if (firstVal !== null) {
          for (const d of dates) {
            if (!filled.has(d)) filled.set(d, firstVal);
            else break;
          }
        }
        return filled;
      };

      const filledMood = fillGaps(moodMap, allDates);
      const filledMarket = fillGaps(marketMap, allDates);

      const moodLineFilled = {
        id: "Social Mood",
        data: allDates
          .filter((d) => filledMood.has(d))
          .map((d) => ({ x: d, y: filledMood.get(d)! })),
      };
      const marketLineFilled = {
        id: "Market Index",
        data: allDates
          .filter((d) => filledMarket.has(d))
          .map((d) => ({ x: d, y: filledMarket.get(d)! })),
      };

      const series: DefaultSeries[] = [moodLineFilled, marketLineFilled];

      // Latest values and divergence
      const latestMood =
        moodLineFilled.data[moodLineFilled.data.length - 1]?.y ?? 0;
      const latestMarket =
        marketLineFilled.data[marketLineFilled.data.length - 1]?.y ?? 50;
      const divergence = Math.abs(latestMood - latestMarket);
      let divergenceStatus = "";
      if (divergence > 20) divergenceStatus = "High Divergence";
      else if (divergence > 10) divergenceStatus = "Moderate Divergence";
      else divergenceStatus = "Aligned";

      return {
        chartData: series,
        latestMood,
        latestMarket,
        divergence,
        divergenceStatus,
      };
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
          <LineChart data={chartData} height={300} yMin={0} yMax={100} colors={["#1f77b4", "#2E7D32"]} />
          <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
            <MetricCard
              label={<><span className="mr-1.5 inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: "#1f77b4" }} />Social Mood</>}
              value={Math.round(latestMood)}
              sublabel="/100"
            />
            <MetricCard
              label={<><span className="mr-1.5 inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: "#2E7D32" }} />Market Index</>}
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
