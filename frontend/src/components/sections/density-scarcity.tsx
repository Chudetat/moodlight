"use client";

import { useMemo } from "react";
import { useTopicVLDS } from "@/lib/hooks/use-api";
import { BarChart } from "@/components/charts/bar-chart";
import { HelperButton } from "@/components/shared/helper-button";
import { ChartSkeleton } from "@/components/shared/loading-skeleton";

export function DensityScarcity() {
  const { data, isLoading } = useTopicVLDS();

  const { densityData, scarcityData, densitySummary, scarcitySummary } =
    useMemo(() => {
      const densityData = (data?.topic_density ?? [])
        .map((d) => ({
          topic: d.scope_name,
          density: Math.round(d.metric_value * 100) / 100,
        }))
        .sort((a, b) => b.density - a.density)
        .slice(0, 12);

      const scarcityData = (data?.topic_scarcity ?? [])
        .map((d) => ({
          topic: d.scope_name,
          scarcity: Math.round(d.metric_value * 100) / 100,
        }))
        .sort((a, b) => b.scarcity - a.scarcity)
        .slice(0, 12);

      const densitySummary = densityData
        .map((d) => `${d.topic}: ${d.density}`)
        .join("\n");
      const scarcitySummary = scarcityData
        .map((d) => `${d.topic}: ${d.scarcity}`)
        .join("\n");

      return { densityData, scarcityData, densitySummary, scarcitySummary };
    }, [data]);

  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2">
        <ChartSkeleton />
        <ChartSkeleton />
      </div>
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {/* Density */}
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="mb-2 flex items-center gap-2">
          <p className="text-sm font-medium">Density (Saturation)</p>
          <HelperButton chartType="density" dataSummary={densitySummary} />
        </div>
        {densityData.length > 0 ? (
          <BarChart
            data={densityData}
            keys={["density"]}
            indexBy="topic"
            layout="horizontal"
            height={Math.max(200, densityData.length * 28)}
            colors={["#60A5FA"]}
          />
        ) : (
          <p className="py-4 text-center text-sm text-muted-foreground">
            No density data.
          </p>
        )}
      </div>

      {/* Scarcity */}
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="mb-2 flex items-center gap-2">
          <p className="text-sm font-medium">Scarcity (Opportunity)</p>
          <HelperButton chartType="scarcity" dataSummary={scarcitySummary} />
        </div>
        {scarcityData.length > 0 ? (
          <BarChart
            data={scarcityData}
            keys={["scarcity"]}
            indexBy="topic"
            layout="horizontal"
            height={Math.max(200, scarcityData.length * 28)}
            colors={["#21C354"]}
          />
        ) : (
          <p className="py-4 text-center text-sm text-muted-foreground">
            No scarcity data.
          </p>
        )}
      </div>
    </div>
  );
}
