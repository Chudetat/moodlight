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

  const { threatIntensity, hotspots, topicTrends, topicChanges, newTopics } = useMemo(() => {
    const items = data?.data ?? [];
    if (items.length === 0)
      return { threatIntensity: 0, hotspots: [], topicTrends: [], topicChanges: [], newTopics: [] };

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

    // Geographic hotspots: top 15 countries by avg intensity (matching Streamlit)
    const countryData = new Map<string, { total: number; count: number }>();
    for (const item of items) {
      if (item.country && item.country !== "Unknown") {
        const existing = countryData.get(item.country) || { total: 0, count: 0 };
        existing.total += item.intensity ?? 0;
        existing.count += 1;
        countryData.set(item.country, existing);
      }
    }
    const hotspots = Array.from(countryData.entries())
      .filter(([, d]) => d.count >= 10)
      .map(([country, d]) => ({
        country,
        avg_intensity: Math.round((d.total / d.count) * 100) / 100,
      }))
      .sort((a, b) => b.avg_intensity - a.avg_intensity)
      .slice(0, 15);

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

    // Topic Trends 24h % change (matching Streamlit create_trend_indicators)
    const now = Date.now();
    const h24 = 24 * 60 * 60 * 1000;
    const recentCount = new Map<string, number>();
    const prevCount = new Map<string, number>();
    for (const item of items) {
      const t = item.topic;
      if (!t || t === "null" || t === "") continue;
      const ts = new Date(item.created_at).getTime();
      if (isNaN(ts)) continue;
      const age = now - ts;
      if (age <= h24) {
        recentCount.set(t, (recentCount.get(t) || 0) + 1);
      } else if (age <= 2 * h24) {
        prevCount.set(t, (prevCount.get(t) || 0) + 1);
      }
    }

    const topicChanges: { topic: string; change_pct: number; recent: number }[] = [];
    const newTopics: { topic: string; recent: number }[] = [];
    for (const [topic, recent] of recentCount.entries()) {
      if (recent < 5) continue;
      const prev = prevCount.get(topic) ?? 0;
      if (prev === 0) {
        newTopics.push({ topic, recent });
        continue;
      }
      const changePct = Math.round(((recent - prev) / prev) * 1000) / 10;
      topicChanges.push({ topic, change_pct: changePct, recent });
    }
    topicChanges.sort((a, b) => Math.abs(b.change_pct) - Math.abs(a.change_pct));
    topicChanges.splice(15);
    newTopics.sort((a, b) => b.recent - a.recent);

    return { threatIntensity, hotspots, topicTrends, topicChanges, newTopics };
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
              colors={["#1f77b4"]}
            />
          </div>
        )}
      </div>

      {/* Topic Trends 24h % change */}
      {topicChanges.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="mb-2 text-sm font-medium">Topic Trends (24h % change)</p>
          <BarChart
            data={topicChanges}
            keys={["change_pct"]}
            indexBy="topic"
            layout="horizontal"
            height={Math.max(300, topicChanges.length * 32)}
            colors={(datum) => {
              const val = typeof datum.data?.change_pct === "number" ? datum.data.change_pct : 0;
              return val > 0 ? "#22C55E" : "#EF4444";
            }}
          />
          {newTopics.length > 0 && (
            <p className="mt-2 text-xs text-muted-foreground">
              New topics this period: {newTopics.map((t) => `${t.topic} (${t.recent})`).join(", ")}
            </p>
          )}
        </div>
      )}

      {/* Geographic hotspots */}
      {hotspots.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="mb-2 flex items-center gap-2">
            <p className="text-sm font-medium">Geographic Hotspots</p>
            <HelperButton
              chartType="geographic_hotspots"
              dataSummary={hotspots
                .map((d) => `${d.country}: ${d.avg_intensity.toFixed(2)}`)
                .join("\n")}
            />
          </div>
          <BarChart
            data={hotspots}
            keys={["avg_intensity"]}
            indexBy="country"
            layout="horizontal"
            height={Math.max(200, hotspots.length * 30)}
            colors={(datum) => {
              const val = typeof datum.data?.avg_intensity === "number" ? datum.data.avg_intensity : 0;
              const intensity = Math.max(0.3, val / 5);
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
