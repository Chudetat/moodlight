"use client";

import { useMemo } from "react";
import { useCombinedData } from "@/lib/hooks/use-api";
import { normalizeEmpathyScore } from "@/lib/utils";
import { ScatterChart, type ScatterSeries } from "@/components/charts/scatter-chart";
import { HelperButton } from "@/components/shared/helper-button";
import { ChartSkeleton } from "@/components/shared/loading-skeleton";

export function ViralityEmpathy() {
  const { data, isLoading } = useCombinedData(7);

  const { chartData, dataSummary } = useMemo(() => {
    const items = data?.data ?? [];
    if (items.length === 0)
      return { chartData: [] as ScatterSeries[], dataSummary: "No data" };

    // Compute virality as log(engagement + 1) * intensity
    const points = items
      .filter((d) => d.engagement > 0)
      .map((d) => ({
        x: Math.log10(d.engagement + 1) * d.intensity,
        y: normalizeEmpathyScore(d.empathy_score),
        size: Math.min(20, Math.max(4, Math.log10(d.engagement + 1) * 3)),
        label: d.text?.slice(0, 60) || "",
      }))
      .slice(0, 300);

    const chartData: ScatterSeries[] = [{ id: "Content", data: points }];

    // Summary for helper button
    const avgVirality =
      points.length > 0
        ? points.reduce((s, p) => s + p.x, 0) / points.length
        : 0;
    const avgEmpathy =
      points.length > 0
        ? points.reduce((s, p) => s + p.y, 0) / points.length
        : 0;
    const dataSummary = `Total items: ${points.length}\nAvg Virality: ${avgVirality.toFixed(2)}\nAvg Empathy: ${avgEmpathy.toFixed(1)}`;

    return { chartData, dataSummary };
  }, [data]);

  if (isLoading) return <ChartSkeleton />;

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-2 flex items-center gap-2">
        <p className="text-sm font-medium">Virality x Empathy</p>
        <HelperButton
          chartType="virality_empathy"
          dataSummary={dataSummary}
        />
      </div>
      {chartData.length > 0 && chartData[0].data.length > 0 ? (
        <ScatterChart
          data={chartData}
          height={350}
          xLabel="Virality Score"
          yLabel="Empathy Score"
          colors={["#FF6B6B"]}
        />
      ) : (
        <p className="py-4 text-center text-sm text-muted-foreground">
          No engagement data available.
        </p>
      )}
    </div>
  );
}
