"use client";

import { useMemo } from "react";
import { useTopicVLDS } from "@/lib/hooks/use-api";
import { BarChart } from "@/components/charts/bar-chart";
import { HelperButton } from "@/components/shared/helper-button";
import { ChartSkeleton } from "@/components/shared/loading-skeleton";
import { OPPORTUNITY_COLORS } from "@/lib/constants";

export function DensityScarcity() {
  const { data, isLoading } = useTopicVLDS();

  const { densityData, scarcityData, densitySummary, scarcitySummary, highOpportunity, saturated } =
    useMemo(() => {
      const densityData = (data?.topic_density ?? [])
        .map((d) => ({
          topic: d.topic,
          density: Math.round((d.density_score ?? 0) * 100) / 100,
        }))
        .sort((a, b) => b.density - a.density)
        .slice(0, 12);

      const scarcityData = (data?.topic_scarcity ?? [])
        .map((d) => ({
          topic: d.topic,
          scarcity: Math.round((d.scarcity_score ?? 0) * 100) / 100,
          opportunity: d.opportunity_level || (
            (d.scarcity_score ?? 0) >= 0.7 ? "HIGH" :
            (d.scarcity_score ?? 0) >= 0.4 ? "MEDIUM" : "LOW"
          ),
        }))
        .sort((a, b) => b.scarcity - a.scarcity)
        .slice(0, 12);

      const highOpportunity = scarcityData
        .filter((d) => d.opportunity === "HIGH")
        .map((d) => d.topic);
      const saturated = densityData
        .filter((d) => d.density >= 0.7)
        .map((d) => d.topic);

      const densitySummary = densityData
        .map((d) => `${d.topic}: ${d.density}`)
        .join("\n");
      const scarcitySummary = scarcityData
        .map((d) => `${d.topic}: ${d.scarcity} (${d.opportunity})`)
        .join("\n");

      return { densityData, scarcityData, densitySummary, scarcitySummary, highOpportunity, saturated };
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
          <p className="text-sm font-medium">Density: Where Conversations Are Concentrated</p>
          <HelperButton chartType="density" dataSummary={densitySummary} />
        </div>
        <p className="mb-2 text-xs text-muted-foreground">
          How crowded is the conversation? High density = be louder or smarter.
        </p>
        {saturated.length > 0 && (
          <p className="mb-2 text-xs text-muted-foreground">
            Most saturated: {saturated.slice(0, 3).join(", ")}
          </p>
        )}
        {densityData.length > 0 ? (
          <BarChart
            data={densityData}
            keys={["density"]}
            indexBy="topic"
            layout="horizontal"
            height={Math.max(200, densityData.length * 28)}
            colors={(datum) => {
              const v = typeof datum.data?.density === "number" ? datum.data.density : 0;
              if (v >= 0.7) return "#1E3A5F";
              if (v >= 0.4) return "#3B7DD8";
              return "#93C5FD";
            }}
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
          <p className="text-sm font-medium">Scarcity: Topic Opportunity Gaps</p>
          <HelperButton chartType="scarcity" dataSummary={scarcitySummary} />
        </div>
        <p className="mb-2 text-xs text-muted-foreground">
          White space&mdash;underserved topics where you can own the narrative.
        </p>
        {highOpportunity.length > 0 && (
          <p className="mb-2 text-xs text-muted-foreground">
            High opportunity: {highOpportunity.slice(0, 3).join(", ")}
          </p>
        )}
        {highOpportunity.length > 0 && (
          <p className="mb-2 text-xs text-blue-400">
            {highOpportunity.length} topic{highOpportunity.length !== 1 ? "s" : ""} with HIGH scarcity &mdash; white space opportunities for thought leadership.
          </p>
        )}
        {scarcityData.length > 0 ? (
          <BarChart
            data={scarcityData}
            keys={["scarcity"]}
            indexBy="topic"
            layout="horizontal"
            height={Math.max(200, scarcityData.length * 28)}
            colors={(datum) => {
              const v = typeof datum.data?.scarcity === "number" ? datum.data.scarcity : 0;
              if (v >= 0.7) return OPPORTUNITY_COLORS.HIGH;
              if (v >= 0.4) return OPPORTUNITY_COLORS.MEDIUM;
              return OPPORTUNITY_COLORS.LOW;
            }}
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
