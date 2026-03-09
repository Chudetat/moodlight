"use client";

import { useMemo } from "react";
import { useCombinedData } from "@/lib/hooks/use-api";
import { normalizeEmpathyScore } from "@/lib/utils";
import { ScatterChart, type ScatterSeries } from "@/components/charts/scatter-chart";
import { HelperButton } from "@/components/shared/helper-button";
import { ChartSkeleton } from "@/components/shared/loading-skeleton";

export function TrendingHeadlines() {
  const { data, isLoading } = useCombinedData(7);

  const { chartData, insights } = useMemo(() => {
    const items = data?.data ?? [];
    if (items.length === 0) return { chartData: [] as ScatterSeries[], insights: [] };

    const now = Date.now();
    const points = items
      .filter((d) => d._source_table === "news_scored" && d.text)
      .map((d) => {
        const ageHours =
          (now - new Date(d.created_at).getTime()) / (1000 * 60 * 60);
        return {
          x: Math.round(ageHours * 10) / 10,
          y: normalizeEmpathyScore(d.empathy_score),
          label: d.text.slice(0, 200),
        };
      })
      .slice(0, 200);

    const chartData: ScatterSeries[] = [{ id: "Headlines", data: points }];

    // Top 5 by empathy score for insights
    const insights = [...points]
      .sort((a, b) => b.y - a.y)
      .slice(0, 5)
      .map((p) => p.label);

    return { chartData, insights };
  }, [data]);

  if (isLoading) return <ChartSkeleton />;

  const dataSummary =
    insights.length > 0
      ? `Top empathetic headlines:\n${insights.join("\n")}`
      : "No headlines";

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-2 flex items-center gap-2">
        <p className="text-sm font-medium">Trending Headlines</p>
        <HelperButton
          chartType="trending_headlines"
          dataSummary={dataSummary}
        />
      </div>
      {chartData.length > 0 && chartData[0].data.length > 0 ? (
        <ScatterChart
          data={chartData}
          height={350}
          xLabel="Age (hours)"
          yLabel="Empathy Score"
          colors={["#60A5FA"]}
        />
      ) : (
        <p className="py-4 text-center text-sm text-muted-foreground">
          No headline data available.
        </p>
      )}
    </div>
  );
}
