"use client";

import { useMemo } from "react";
import { useCombinedData } from "@/lib/hooks/use-api";
import { normalizeEmpathyScore } from "@/lib/utils";
import { LineChart } from "@/components/charts/line-chart";
import { HelperButton } from "@/components/shared/helper-button";
import { ChartSkeleton } from "@/components/shared/loading-skeleton";
import type { DefaultSeries } from "@nivo/line";

export function MoodHistory() {
  const { data, isLoading } = useCombinedData(7);

  const chartData = useMemo<DefaultSeries[]>(() => {
    if (!data?.data?.length) return [];

    // Group by date, compute daily avg empathy
    const byDate = new Map<string, number[]>();
    for (const item of data.data) {
      const date = item.created_at.slice(0, 10); // YYYY-MM-DD
      const list = byDate.get(date) || [];
      list.push(item.empathy_score);
      byDate.set(date, list);
    }

    const points = Array.from(byDate.entries())
      .map(([date, scores]) => ({
        x: date,
        y: normalizeEmpathyScore(
          scores.reduce((a, b) => a + b, 0) / scores.length
        ),
      }))
      .sort((a, b) => a.x.localeCompare(b.x));

    return [{ id: "Mood Score", data: points }];
  }, [data]);

  if (isLoading) {
    return (
      <div>
        <h2 className="mb-1 text-lg font-semibold">7-Day Mood History</h2>
        <ChartSkeleton />
      </div>
    );
  }

  // Build data summary for helper button
  const dataSummary =
    chartData[0]?.data
      .map((p) => `${p.x}: ${p.y}`)
      .join("\n") || "No data";

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <h2 className="text-lg font-semibold">7-Day Mood History</h2>
        {chartData.length > 0 && (
          <HelperButton
            chartType="mood_history"
            dataSummary={dataSummary}
          />
        )}
      </div>
      {chartData[0]?.data.length ? (
        <div className="rounded-lg border border-border bg-card p-4">
          <LineChart
            data={chartData}
            height={300}
            enableArea
            yFormat=" >-.0f"
            axisLeftFormat=" >-.0f"
          />
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          No mood data available for the last 7 days.
        </p>
      )}
    </div>
  );
}
