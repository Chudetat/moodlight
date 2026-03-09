"use client";

import { useMemo } from "react";
import { useCombinedData } from "@/lib/hooks/use-api";
import { FeatureGate } from "@/components/layout/feature-gate";
import { GaugeChart } from "@/components/charts/gauge-chart";
import { BarChart } from "@/components/charts/bar-chart";
import { HelperButton } from "@/components/shared/helper-button";
import { ChartSkeleton } from "@/components/shared/loading-skeleton";

function DashboardContent() {
  const { data, isLoading } = useCombinedData(7);

  const { threatIntensity, hotspots, topicTrends } = useMemo(() => {
    const items = data?.data ?? [];
    if (items.length === 0)
      return { threatIntensity: 0, hotspots: [], topicTrends: [] };

    // Threat intensity: MEDIAN of all intensity values (raw 0-5 scale, matching Streamlit)
    const intensities = items
      .map((d) => d.intensity)
      .filter((v) => typeof v === "number" && !isNaN(v))
      .sort((a, b) => a - b);
    const mid = Math.floor(intensities.length / 2);
    const threatIntensity =
      intensities.length > 0
        ? intensities.length % 2 === 0
          ? (intensities[mid - 1] + intensities[mid]) / 2
          : intensities[mid]
        : 0;

    // Geographic hotspots: top 10 countries by count
    const countryCount = new Map<string, number>();
    for (const item of items) {
      if (item.country) {
        countryCount.set(
          item.country,
          (countryCount.get(item.country) || 0) + 1
        );
      }
    }
    const hotspots = Array.from(countryCount.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([country, count]) => ({ country, count }));

    // Topic trends: count per topic (top 20 like Streamlit)
    const topicCount = new Map<string, number>();
    for (const item of items) {
      if (item.topic) {
        topicCount.set(
          item.topic,
          (topicCount.get(item.topic) || 0) + 1
        );
      }
    }
    const topicTrends = Array.from(topicCount.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 20)
      .map(([topic, count]) => ({ topic, count }));

    return { threatIntensity, hotspots, topicTrends };
  }, [data]);

  if (isLoading) {
    return <ChartSkeleton />;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start gap-6">
        {/* Threat gauge */}
        <div className="rounded-lg border border-border bg-card p-4">
          <GaugeChart
            value={threatIntensity}
            label="Threat Intensity"
          />
        </div>

        {/* IC Topic Breakdown */}
        {topicTrends.length > 0 && (
          <div className="flex-1 rounded-lg border border-border bg-card p-4">
            <p className="mb-2 text-sm font-medium">IC Topic Breakdown</p>
            <BarChart
              data={topicTrends}
              keys={["count"]}
              indexBy="topic"
              layout="horizontal"
              height={Math.max(300, topicTrends.length * 22)}
              colors={["#60A5FA"]}
            />
          </div>
        )}
      </div>

      {/* Geographic hotspots */}
      {hotspots.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="mb-2 flex items-center gap-2">
            <p className="text-sm font-medium">Geographic Hotspots</p>
            <HelperButton
              chartType="geographic_hotspots"
              dataSummary={hotspots
                .map((d) => `${d.country}: ${d.count}`)
                .join("\n")}
            />
          </div>
          <BarChart
            data={hotspots}
            keys={["count"]}
            indexBy="country"
            layout="horizontal"
            height={Math.max(200, hotspots.length * 30)}
            colors={(datum) => {
              const maxCount = hotspots[0]?.count || 1;
              const val = typeof datum.data?.count === "number" ? datum.data.count : 0;
              const intensity = Math.max(0.3, val / maxCount);
              const r = 220;
              const g = Math.round(60 * (1 - intensity));
              const b = Math.round(60 * (1 - intensity));
              return `rgb(${r},${g},${b})`;
            }}
          />
        </div>
      )}
    </div>
  );
}

export function IntelDashboard() {
  return (
    <div>
      <h2 className="mb-1 text-lg font-semibold">
        Intelligence Dashboard
      </h2>
      <FeatureGate feature="intelligence_dashboard">
        <DashboardContent />
      </FeatureGate>
    </div>
  );
}
