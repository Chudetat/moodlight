"use client";

import { useCombinedData } from "@/lib/hooks/use-api";
import { normalizeEmpathyScore } from "@/lib/utils";
import { getEmpathyLabel, getEmpathyEmoji } from "@/lib/constants";
import { MetricCard } from "@/components/charts/metric-card";
import { MetricSkeleton } from "@/components/shared/loading-skeleton";

export function CulturalPulse() {
  const { data, isLoading } = useCombinedData(7);

  if (isLoading) {
    return (
      <div>
        <h2 className="mb-1 text-lg font-semibold">Cultural Pulse</h2>
        <MetricSkeleton />
      </div>
    );
  }

  // Calculate global mood from last 24h data
  const items = data?.data ?? [];
  const now = Date.now();
  const oneDayAgo = now - 24 * 60 * 60 * 1000;
  const recent = items.filter(
    (d) => new Date(d.created_at).getTime() > oneDayAgo
  );
  const rawAvg =
    recent.length > 0
      ? recent.reduce((sum, d) => sum + d.empathy_score, 0) / recent.length
      : 0;
  const moodScore = normalizeEmpathyScore(rawAvg);
  const label = getEmpathyLabel(moodScore);
  const emoji = getEmpathyEmoji(moodScore);

  return (
    <div>
      <h2 className="mb-1 text-lg font-semibold">Cultural Pulse</h2>
      <MetricCard
        label="Global Mood Score"
        value={moodScore}
        emoji={emoji}
        sublabel={label}
        className="max-w-xs"
      />
    </div>
  );
}
