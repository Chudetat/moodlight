"use client";

import { useMemo } from "react";
import { useAuth } from "@/lib/hooks/use-auth";
import { useDashboardStore } from "@/store/dashboard-store";
import { useBrands, useTopics, useMetricTrends } from "@/lib/hooks/use-api";
import { LineChart } from "@/components/charts/line-chart";
import { MetricCard } from "@/components/charts/metric-card";
import { ChartSkeleton } from "@/components/shared/loading-skeleton";
import type { DefaultSeries } from "@nivo/line";

function GlobalMoodTrend({ days }: { days: number }) {
  const { data, isLoading } = useMetricTrends("global", undefined, days);

  const { chartData, trendDelta } = useMemo(() => {
    const items = (data?.data ?? []).filter(
      (d) => d.metric_name === "avg_empathy_news"
    );
    if (items.length === 0) return { chartData: [] as DefaultSeries[], trendDelta: null };

    const sorted = [...items].sort((a, b) =>
      a.snapshot_date.localeCompare(b.snapshot_date)
    );

    const points = sorted.map((d) => ({
      x: d.snapshot_date,
      y: d.metric_value,
    }));

    const chartData: DefaultSeries[] = [{ id: "Global Mood", data: points }];

    // Month-over-month delta
    let trendDelta: { recent: number; delta: number } | null = null;
    if (sorted.length >= 2) {
      const mid = Math.floor(sorted.length / 2);
      const recentAvg =
        sorted.slice(mid).reduce((s, d) => s + d.metric_value, 0) /
        (sorted.length - mid);
      const priorAvg =
        sorted.slice(0, mid).reduce((s, d) => s + d.metric_value, 0) / mid;
      const deltaPct = priorAvg !== 0 ? ((recentAvg - priorAvg) / priorAvg) * 100 : 0;
      trendDelta = { recent: recentAvg, delta: deltaPct };
    }

    return { chartData, trendDelta };
  }, [data]);

  if (isLoading) return <ChartSkeleton />;

  if (chartData.length === 0 || chartData[0].data.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No global mood snapshots available yet. Data accumulates daily.
      </p>
    );
  }

  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold">Global Mood Trend</h3>
      <LineChart data={chartData} height={250} colors={["#1f77b4"]} />
      {trendDelta && (
        <div className="mt-2">
          <MetricCard
            label="Mood Trend"
            value={trendDelta.recent.toFixed(2)}
            sublabel={`${trendDelta.delta >= 0 ? "+" : ""}${trendDelta.delta.toFixed(1)}% vs prior period`}
          />
        </div>
      )}
    </div>
  );
}

function BrandTrend({ brand, days }: { brand: string; days: number }) {
  const { data, isLoading } = useMetricTrends("brand", brand, days);

  const chartData = useMemo(() => {
    const items = data?.data ?? [];
    if (items.length === 0) return [] as DefaultSeries[];

    // Group by metric_name
    const byMetric = new Map<string, { x: string; y: number }[]>();
    for (const item of items) {
      const key = item.metric_name;
      if (!byMetric.has(key)) byMetric.set(key, []);
      byMetric.get(key)!.push({ x: item.snapshot_date, y: item.metric_value });
    }

    return Array.from(byMetric.entries()).map(([name, points]) => ({
      id: name,
      data: points.sort((a, b) => a.x.localeCompare(b.x)),
    }));
  }, [data]);

  if (isLoading) return <ChartSkeleton />;

  if (chartData.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No trend data for {brand} yet
      </p>
    );
  }

  return (
    <div>
      <h4 className="mb-1 text-xs font-medium">{brand}</h4>
      <LineChart data={chartData} height={200} />
    </div>
  );
}

function TopicTrend({ topic, days }: { topic: string; days: number }) {
  const { data, isLoading } = useMetricTrends("topic", topic, days);

  const chartData = useMemo(() => {
    const items = data?.data ?? [];
    if (items.length === 0) return [] as DefaultSeries[];

    const byMetric = new Map<string, { x: string; y: number }[]>();
    for (const item of items) {
      const key = item.metric_name;
      if (!byMetric.has(key)) byMetric.set(key, []);
      byMetric.get(key)!.push({ x: item.snapshot_date, y: item.metric_value });
    }

    return Array.from(byMetric.entries()).map(([name, points]) => ({
      id: name,
      data: points.sort((a, b) => a.x.localeCompare(b.x)),
    }));
  }, [data]);

  if (isLoading) return <ChartSkeleton />;

  if (chartData.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No trend data for {topic} yet
      </p>
    );
  }

  return (
    <div>
      <h4 className="mb-1 text-xs font-medium">{topic}</h4>
      <LineChart data={chartData} height={200} />
    </div>
  );
}

export function HistoricalTrends() {
  const days = useDashboardStore((s) => s.days);
  const { username } = useAuth();
  const { data: brandsData } = useBrands(username);
  const { data: topicsData } = useTopics(username);

  // Only show when time range > 7 days
  if (days <= 7) return null;

  const brands = brandsData?.brands ?? [];
  const topics = (topicsData?.topics ?? []).map((t) => t.topic_name);

  return (
    <div>
      <h2 className="mb-1 text-lg font-semibold">Historical Trends</h2>
      <p className="mb-3 text-xs text-muted-foreground">
        Dashboard charts above show the latest 7 days of live data. Below are
        longer-range views from daily metric snapshots.
      </p>

      <div className="space-y-6">
        <GlobalMoodTrend days={days} />

        {brands.length > 0 && (
          <div>
            <h3 className="mb-2 text-sm font-semibold">Brand Trends</h3>
            <div className="space-y-4">
              {brands.map((brand) => (
                <BrandTrend key={brand} brand={brand} days={days} />
              ))}
            </div>
          </div>
        )}

        {topics.length > 0 && (
          <div>
            <h3 className="mb-2 text-sm font-semibold">Topic Trends</h3>
            <div className="space-y-4">
              {topics.map((topic) => (
                <TopicTrend key={topic} topic={topic} days={days} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
