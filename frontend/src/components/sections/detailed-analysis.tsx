"use client";

import { useMemo } from "react";
import { useCombinedData } from "@/lib/hooks/use-api";
import { normalizeEmpathyScore } from "@/lib/utils";
import { BarChart } from "@/components/charts/bar-chart";
import { HelperButton } from "@/components/shared/helper-button";
import { ChartSkeleton } from "@/components/shared/loading-skeleton";
import { EMOTION_COLORS, EMPATHY_COLORS, EMPATHY_LABELS } from "@/lib/constants";

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
          colors={(datum) => {
            const v = typeof datum.data?.empathy === "number" ? datum.data.empathy : 0;
            if (v < 35) return EMPATHY_COLORS[0];
            if (v < 50) return EMPATHY_COLORS[1];
            if (v < 70) return EMPATHY_COLORS[2];
            return EMPATHY_COLORS[3];
          }}
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
      const emotion = item.emotion_top_1;
      if (emotion) {
        emotionCount.set(emotion, (emotionCount.get(emotion) || 0) + 1);
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
                  {["\uD83E\uDD47", "\uD83E\uDD48", "\uD83E\uDD49"][i]}
                </span>{" "}
                <span className="font-medium">{d.emotion}</span>{" "}
                <span className="text-muted-foreground">({d.count})</span>
              </div>
            ))}
          </div>
          <BarChart
            data={chartData}
            keys={["count"]}
            indexBy="emotion"
            layout="horizontal"
            height={Math.max(250, chartData.length * 28)}
            colors={(datum) => {
              const emotion = String(datum.indexValue || "").toLowerCase();
              return EMOTION_COLORS[emotion] || "#808080";
            }}
          />
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
      { label: EMPATHY_LABELS[0], min: 0, max: 35, count: 0 },
      { label: EMPATHY_LABELS[1], min: 35, max: 50, count: 0 },
      { label: EMPATHY_LABELS[2], min: 50, max: 70, count: 0 },
      { label: EMPATHY_LABELS[3], min: 70, max: 101, count: 0 },
    ];
    for (const item of items) {
      const score = normalizeEmpathyScore(item.empathy_score);
      const bucket = buckets.find((b) => score >= b.min && score < b.max);
      if (bucket) bucket.count++;
    }
    return buckets.map((b) => ({ range: b.label, count: b.count }));
  }, [data]);

  if (isLoading) return <ChartSkeleton />;

  const total = chartData.reduce((s, d) => s + d.count, 0);
  const dataSummary = chartData
    .map((d) => `${d.range}: ${d.count}`)
    .join("\n");

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-2 flex items-center gap-2">
        <p className="text-sm font-medium">Empathy Distribution</p>
        <HelperButton chartType="empathy_distribution" dataSummary={dataSummary} />
      </div>
      {total > 0 && (
        <div className="mb-3 flex gap-3">
          {chartData
            .filter((d) => d.count > 0)
            .sort((a, b) => b.count - a.count)
            .slice(0, 3)
            .map((d, i) => (
              <div key={d.range} className="text-xs">
                <span className="text-muted-foreground">
                  {["\uD83E\uDD47", "\uD83E\uDD48", "\uD83E\uDD49"][i]}
                </span>{" "}
                <span className="font-medium">{d.range}</span>{" "}
                <span className="text-muted-foreground">
                  ({total > 0 ? Math.round((d.count / total) * 100) : 0}%)
                </span>
              </div>
            ))}
        </div>
      )}
      <BarChart
        data={chartData}
        keys={["count"]}
        indexBy="range"
        layout="horizontal"
        height={200}
        colors={(datum) => {
          const range = String(datum.indexValue || "");
          const idx = EMPATHY_LABELS.indexOf(range);
          return idx >= 0 ? EMPATHY_COLORS[idx] : "#808080";
        }}
      />
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
                  {["\uD83E\uDD47", "\uD83E\uDD48", "\uD83E\uDD49"][i]}
                </span>{" "}
                <span className="font-medium capitalize">{d.topic}</span>{" "}
                <span className="text-muted-foreground">({d.count})</span>
              </div>
            ))}
          </div>
          <BarChart
            data={chartData}
            keys={["count"]}
            indexBy="topic"
            layout="horizontal"
            height={Math.max(300, chartData.length * 28)}
            colors={["#1f77b4"]}
          />
        </>
      ) : (
        <p className="py-4 text-center text-sm text-muted-foreground">No data</p>
      )}
    </div>
  );
}
