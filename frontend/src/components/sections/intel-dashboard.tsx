"use client";

import { useMemo } from "react";
import { useCombinedData } from "@/lib/hooks/use-api";
import { normalizeEmpathyScore } from "@/lib/utils";
import { FeatureGate } from "@/components/layout/feature-gate";
import { GaugeChart } from "@/components/charts/gauge-chart";
import { BarChart } from "@/components/charts/bar-chart";
import { ChartSkeleton } from "@/components/shared/loading-skeleton";

function DashboardContent() {
  const { data, isLoading } = useCombinedData(7);

  const { threatIntensity, hotspots, topicTrends } = useMemo(() => {
    const items = data?.data ?? [];
    if (items.length === 0)
      return { threatIntensity: 0, hotspots: [], topicTrends: [] };

    // Threat intensity: avg intensity of last 24h
    const now = Date.now();
    const oneDayAgo = now - 24 * 60 * 60 * 1000;
    const recent = items.filter(
      (d) => new Date(d.created_at).getTime() > oneDayAgo
    );
    const avgIntensity =
      recent.length > 0
        ? recent.reduce((sum, d) => sum + d.intensity, 0) / recent.length
        : 0;
    const threatIntensity = normalizeEmpathyScore(avgIntensity);

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

    // Topic trends: count per topic
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
      .slice(0, 10)
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

        {/* Geographic hotspots */}
        {hotspots.length > 0 && (
          <div className="flex-1 rounded-lg border border-border bg-card p-4">
            <p className="mb-2 text-sm font-medium">
              Geographic Hotspots
            </p>
            <BarChart
              data={hotspots}
              keys={["count"]}
              indexBy="country"
              layout="horizontal"
              height={Math.max(200, hotspots.length * 30)}
            />
          </div>
        )}
      </div>

      {/* Topic trends */}
      {topicTrends.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="mb-2 text-sm font-medium">Topic Trends</p>
          <BarChart
            data={topicTrends}
            keys={["count"]}
            indexBy="topic"
            height={300}
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
