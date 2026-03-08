"use client";

import { useMemo } from "react";
import { useTopicVLDS } from "@/lib/hooks/use-api";
import { ScatterChart, type ScatterSeries } from "@/components/charts/scatter-chart";
import { HelperButton } from "@/components/shared/helper-button";
import { ChartSkeleton } from "@/components/shared/loading-skeleton";

export function VelocityLongevity() {
  const { data, isLoading } = useTopicVLDS();

  const { chartData, dataSummary, quadrantCounts } = useMemo(() => {
    if (!data)
      return {
        chartData: [] as ScatterSeries[],
        dataSummary: "No data",
        quadrantCounts: { flash: 0, momentum: 0, fading: 0, stable: 0 },
      };

    // Build per-topic map
    const topicMap = new Map<string, { velocity: number; longevity: number }>();
    for (const item of data.topic_longevity ?? []) {
      const existing = topicMap.get(item.scope_name) || {
        velocity: 0,
        longevity: 0,
      };
      existing.longevity = item.metric_value ?? 0;
      topicMap.set(item.scope_name, existing);
    }

    const points = Array.from(topicMap.entries()).map(
      ([topic, { velocity, longevity }]) => ({
        x: velocity,
        y: longevity,
        label: topic,
      })
    );

    // Quadrant counts
    const quadrantCounts = { flash: 0, momentum: 0, fading: 0, stable: 0 };
    for (const p of points) {
      if (p.x > 0.5 && p.y > 0.5) quadrantCounts.momentum++;
      else if (p.x > 0.5 && p.y <= 0.5) quadrantCounts.flash++;
      else if (p.x <= 0.5 && p.y > 0.5) quadrantCounts.stable++;
      else quadrantCounts.fading++;
    }

    const chartData: ScatterSeries[] = [{ id: "Topics", data: points }];
    const dataSummary = points
      .map((p) => `${p.label}: V=${(p.x ?? 0).toFixed(2)}, L=${(p.y ?? 0).toFixed(2)}`)
      .join("\n");

    return { chartData, dataSummary, quadrantCounts };
  }, [data]);

  if (isLoading) return <ChartSkeleton />;

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-2 flex items-center gap-2">
        <p className="text-sm font-medium">Velocity x Longevity</p>
        <HelperButton
          chartType="velocity_longevity"
          dataSummary={dataSummary}
        />
      </div>

      <div className="mb-3 flex gap-4 text-xs">
        <span>
          <span className="font-medium text-green-400">
            {quadrantCounts.momentum}
          </span>{" "}
          Momentum
        </span>
        <span>
          <span className="font-medium text-yellow-400">
            {quadrantCounts.flash}
          </span>{" "}
          Flash Trends
        </span>
        <span>
          <span className="font-medium text-blue-400">
            {quadrantCounts.stable}
          </span>{" "}
          Stable
        </span>
        <span>
          <span className="font-medium text-muted-foreground">
            {quadrantCounts.fading}
          </span>{" "}
          Fading
        </span>
      </div>

      {chartData.length > 0 && chartData[0].data.length > 0 ? (
        <ScatterChart
          data={chartData}
          height={350}
          xLabel="Velocity"
          yLabel="Longevity"
        />
      ) : (
        <p className="py-4 text-center text-sm text-muted-foreground">
          No VLDS data available.
        </p>
      )}
    </div>
  );
}
