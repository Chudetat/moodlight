"use client";

import { useMemo } from "react";
import { useCombinedData } from "@/lib/hooks/use-api";
import { normalizeEmpathyScore } from "@/lib/utils";
import { BarChart } from "@/components/charts/bar-chart";
import { HelperButton } from "@/components/shared/helper-button";
import { ChartSkeleton } from "@/components/shared/loading-skeleton";

export function EmpathyByTopic() {
  const { data, isLoading } = useCombinedData(7);

  const chartData = useMemo(() => {
    const items = data?.data ?? [];
    const byTopic = new Map<string, number[]>();
    for (const item of items) {
      if (!item.topic) continue;
      const list = byTopic.get(item.topic) || [];
      list.push(item.empathy_score);
      byTopic.set(item.topic, list);
    }
    return Array.from(byTopic.entries())
      .map(([topic, scores]) => ({
        topic,
        empathy: normalizeEmpathyScore(
          scores.reduce((a, b) => a + b, 0) / scores.length
        ),
      }))
      .sort((a, b) => b.empathy - a.empathy)
      .slice(0, 15);
  }, [data]);

  if (isLoading) return <ChartSkeleton />;

  const dataSummary = chartData
    .map((d) => `${d.topic}: ${d.empathy}`)
    .join("\n");

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-2 flex items-center gap-2">
        <p className="text-sm font-medium">Empathy by Topic</p>
        <HelperButton chartType="empathy_by_topic" dataSummary={dataSummary} />
      </div>
      {chartData.length > 0 ? (
        <BarChart
          data={chartData}
          keys={["empathy"]}
          indexBy="topic"
          layout="horizontal"
          height={Math.max(250, chartData.length * 30)}
        />
      ) : (
        <p className="py-4 text-center text-sm text-muted-foreground">No data</p>
      )}
    </div>
  );
}

export function EmotionalBreakdown() {
  const { data, isLoading } = useCombinedData(7);

  const chartData = useMemo(() => {
    const items = data?.data ?? [];
    const emotionCount = new Map<string, number>();
    for (const item of items) {
      for (const emotion of [
        item.emotion_top_1,
        item.emotion_top_2,
        item.emotion_top_3,
      ]) {
        if (emotion) {
          emotionCount.set(emotion, (emotionCount.get(emotion) || 0) + 1);
        }
      }
    }
    return Array.from(emotionCount.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 12)
      .map(([emotion, count]) => ({ emotion, count }));
  }, [data]);

  if (isLoading) return <ChartSkeleton />;

  const dataSummary = chartData
    .map((d) => `${d.emotion}: ${d.count}`)
    .join("\n");

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-2 flex items-center gap-2">
        <p className="text-sm font-medium">Emotional Breakdown</p>
        <HelperButton chartType="emotional_breakdown" dataSummary={dataSummary} />
      </div>
      {chartData.length > 0 ? (
        <>
          <div className="mb-3 flex gap-3">
            {chartData.slice(0, 3).map((d, i) => (
              <div key={d.emotion} className="text-xs">
                <span className="text-muted-foreground">
                  {["🥇", "🥈", "🥉"][i]}
                </span>{" "}
                <span className="font-medium">{d.emotion}</span>{" "}
                <span className="text-muted-foreground">({d.count})</span>
              </div>
            ))}
          </div>
          <BarChart data={chartData} keys={["count"]} indexBy="emotion" height={280} />
        </>
      ) : (
        <p className="py-4 text-center text-sm text-muted-foreground">No data</p>
      )}
    </div>
  );
}

export function EmpathyDistribution() {
  const { data, isLoading } = useCombinedData(7);

  const chartData = useMemo(() => {
    const items = data?.data ?? [];
    const buckets = [
      { label: "0-20", min: 0, max: 20, count: 0 },
      { label: "20-40", min: 20, max: 40, count: 0 },
      { label: "40-60", min: 40, max: 60, count: 0 },
      { label: "60-80", min: 60, max: 80, count: 0 },
      { label: "80-100", min: 80, max: 100, count: 0 },
    ];
    for (const item of items) {
      const score = normalizeEmpathyScore(item.empathy_score);
      const bucket = buckets.find((b) => score >= b.min && score < b.max);
      if (bucket) bucket.count++;
      else if (score === 100) buckets[4].count++;
    }
    return buckets.map((b) => ({ range: b.label, count: b.count }));
  }, [data]);

  if (isLoading) return <ChartSkeleton />;

  const dataSummary = chartData
    .map((d) => `${d.range}: ${d.count}`)
    .join("\n");

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-2 flex items-center gap-2">
        <p className="text-sm font-medium">Empathy Distribution</p>
        <HelperButton chartType="empathy_distribution" dataSummary={dataSummary} />
      </div>
      <BarChart data={chartData} keys={["count"]} indexBy="range" height={250} />
    </div>
  );
}

export function TopicDistribution() {
  const { data, isLoading } = useCombinedData(7);

  const chartData = useMemo(() => {
    const items = data?.data ?? [];
    const topicCount = new Map<string, number>();
    for (const item of items) {
      if (item.topic) {
        topicCount.set(item.topic, (topicCount.get(item.topic) || 0) + 1);
      }
    }
    return Array.from(topicCount.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 15)
      .map(([topic, count]) => ({ topic, count }));
  }, [data]);

  if (isLoading) return <ChartSkeleton />;

  const dataSummary = chartData
    .map((d) => `${d.topic}: ${d.count}`)
    .join("\n");

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-2 flex items-center gap-2">
        <p className="text-sm font-medium">Topic Distribution (Top 15)</p>
        <HelperButton chartType="topic_distribution" dataSummary={dataSummary} />
      </div>
      {chartData.length > 0 ? (
        <>
          <div className="mb-3 flex gap-3">
            {chartData.slice(0, 3).map((d, i) => (
              <div key={d.topic} className="text-xs">
                <span className="text-muted-foreground">
                  {["🥇", "🥈", "🥉"][i]}
                </span>{" "}
                <span className="font-medium capitalize">{d.topic}</span>{" "}
                <span className="text-muted-foreground">({d.count})</span>
              </div>
            ))}
          </div>
          <BarChart data={chartData} keys={["count"]} indexBy="topic" height={300} />
        </>
      ) : (
        <p className="py-4 text-center text-sm text-muted-foreground">No data</p>
      )}
    </div>
  );
}
