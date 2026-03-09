"use client";

import { useMemo } from "react";
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
  const { moodScore, label, emoji, recentCount } = useMemo(() => {
    const items = data?.data ?? [];
    const oneDayAgo = Date.now() - 24 * 60 * 60 * 1000;
    const recent = items.filter(
      (d) => new Date(d.created_at).getTime() > oneDayAgo
    );
    const rawAvg =
      recent.length > 0
        ? recent.reduce((sum, d) => sum + d.empathy_score, 0) / recent.length
        : 0;
    const score = normalizeEmpathyScore(rawAvg);
    return {
      moodScore: score,
      label: getEmpathyLabel(score),
      emoji: getEmpathyEmoji(score),
      recentCount: recent.length,
    };
  }, [data]);

  return (
    <div>
      <h2 className="mb-1 text-lg font-semibold">Cultural Pulse</h2>
      <p className="mb-3 text-xs text-muted-foreground">
        The world&rsquo;s emotional temperature&mdash;are audiences receptive or reactive?
      </p>
      <MetricCard
        label="Global Mood Score"
        value={moodScore}
        emoji={emoji}
        sublabel={`${label} \u00B7 Based on ${recentCount} posts`}
        className="max-w-xs"
      />
      <p className="mt-2 text-[10px] text-muted-foreground">
        50 = neutral &middot; Above 50 = warm/supportive &middot; Below 50 = hostile/negative
      </p>
    </div>
  );
}
