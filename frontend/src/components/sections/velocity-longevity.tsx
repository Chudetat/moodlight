"use client";

import { useMemo } from "react";
import { useTopicVLDS } from "@/lib/hooks/use-api";
import { ScatterChart, type ScatterSeries } from "@/components/charts/scatter-chart";
import { HelperButton } from "@/components/shared/helper-button";
import { ChartSkeleton } from "@/components/shared/loading-skeleton";
import { QUADRANT_COLORS } from "@/lib/constants";

export function VelocityLongevity() {
  const { data, isLoading } = useTopicVLDS();

  const { chartData, dataSummary, quadrantCounts } = useMemo(() => {
    if (!data)
      return {
        chartData: [] as ScatterSeries[],
        dataSummary: "No data",
        quadrantCounts: { flash: 0, momentum: 0, fading: 0, stable: 0 },
      };

    const records = data.topic_longevity ?? [];
    if (records.length === 0)
      return {
        chartData: [] as ScatterSeries[],
        dataSummary: "No data",
        quadrantCounts: { flash: 0, momentum: 0, fading: 0, stable: 0 },
      };

    // Normalize velocity by max value (matching Streamlit)
    const maxVelocity = Math.max(
      ...records.map((r) => r.velocity_score ?? 0),
      0.01
    );

    const points = records.map((r) => ({
      x: (r.velocity_score ?? 0) / maxVelocity, // normalized 0-1
      y: r.longevity_score ?? 0,
      label: r.topic,
    }));

    // Median-based thresholds (matching Streamlit)
    const sortedX = points.map((p) => p.x).sort((a, b) => a - b);
    const sortedY = points.map((p) => p.y).sort((a, b) => a - b);
    const midX = Math.floor(sortedX.length / 2);
    const midY = Math.floor(sortedY.length / 2);
    const velMedian = sortedX.length % 2 === 0
      ? (sortedX[midX - 1] + sortedX[midX]) / 2
      : sortedX[midX];
    const lonMedian = sortedY.length % 2 === 0
      ? (sortedY[midY - 1] + sortedY[midY]) / 2
      : sortedY[midY];

    const quadrantCounts = { flash: 0, momentum: 0, fading: 0, stable: 0 };
    for (const p of points) {
      if (p.x > velMedian && p.y > lonMedian) quadrantCounts.momentum++;
      else if (p.x > velMedian && p.y <= lonMedian) quadrantCounts.flash++;
      else if (p.x <= velMedian && p.y > lonMedian) quadrantCounts.stable++;
      else quadrantCounts.fading++;
    }

    // Split into 4 quadrant-colored series
    const quadrantSeries: Record<string, typeof points> = {
      "Lasting Movement": [],
      "Flash Trend": [],
      "Evergreen Topic": [],
      "Fading Out": [],
    };
    for (const p of points) {
      if (p.x > velMedian && p.y > lonMedian) quadrantSeries["Lasting Movement"].push(p);
      else if (p.x > velMedian && p.y <= lonMedian) quadrantSeries["Flash Trend"].push(p);
      else if (p.x <= velMedian && p.y > lonMedian) quadrantSeries["Evergreen Topic"].push(p);
      else quadrantSeries["Fading Out"].push(p);
    }
    const chartData: ScatterSeries[] = Object.entries(quadrantSeries)
      .filter(([, pts]) => pts.length > 0)
      .map(([name, pts]) => ({ id: name, data: pts }));
    const dataSummary = records
      .map(
        (r) =>
          `${r.topic}: V=${(r.velocity_score ?? 0).toFixed(2)}, L=${(r.longevity_score ?? 0).toFixed(2)}`
      )
      .join("\n");

    return { chartData, dataSummary, quadrantCounts };
  }, [data]);

  if (isLoading) return <ChartSkeleton />;

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-1 flex items-center gap-2">
        <p className="text-sm font-medium">Velocity x Longevity: Topic Strategic Value</p>
        <HelperButton
          chartType="velocity_longevity"
          dataSummary={dataSummary}
        />
      </div>
      <p className="mb-2 text-xs text-muted-foreground">
        Is it a flash or a movement? Know before you commit resources.
      </p>

      <div className="mb-3 grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
        <div className="rounded bg-muted/50 p-2 text-center">
          <span className="text-lg font-bold text-green-400">
            {quadrantCounts.momentum}
          </span>
          <p className="text-muted-foreground">Lasting Movement</p>
        </div>
        <div className="rounded bg-muted/50 p-2 text-center">
          <span className="text-lg font-bold text-yellow-400">
            {quadrantCounts.flash}
          </span>
          <p className="text-muted-foreground">Flash Trends</p>
        </div>
        <div className="rounded bg-muted/50 p-2 text-center">
          <span className="text-lg font-bold text-blue-400">
            {quadrantCounts.stable}
          </span>
          <p className="text-muted-foreground">Evergreen</p>
        </div>
        <div className="rounded bg-muted/50 p-2 text-center">
          <span className="text-lg font-bold text-gray-400">
            {quadrantCounts.fading}
          </span>
          <p className="text-muted-foreground">Fading</p>
        </div>
      </div>

      {chartData.length > 0 ? (
        <ScatterChart
          data={chartData}
          height={350}
          xLabel="Velocity (normalized)"
          yLabel="Longevity"
          colors={chartData.map((s) => QUADRANT_COLORS[s.id] || "#808080")}
        />
      ) : (
        <p className="py-4 text-center text-sm text-muted-foreground">
          No VLDS data available.
        </p>
      )}
    </div>
  );
}
