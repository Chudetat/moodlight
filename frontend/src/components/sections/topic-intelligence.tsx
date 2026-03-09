"use client";

import { useAuth } from "@/lib/hooks/use-auth";
import { useTopicVLDS, useAlerts, useCombinedData, useTopics } from "@/lib/hooks/use-api";
import { normalizeEmpathyScore } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { HelperButton } from "@/components/shared/helper-button";
import { CardListSkeleton } from "@/components/shared/loading-skeleton";
import { SEVERITY_ICONS } from "@/lib/constants";

function getStrategicLabel(
  v: number,
  l: number,
  d: number,
  s: number
): { label: string; color: string } {
  // Thresholds match Streamlit app.py lines 3854-3869
  if (v >= 0.7 && l >= 0.7 && d < 0.5 && s >= 0.5)
    return { label: "First Mover Opportunity", color: "#22C55E" };
  if (v >= 0.7 && l >= 0.7 && d >= 0.7 && s < 0.3)
    return { label: "Red Ocean", color: "#EF4444" };
  if (v >= 0.7 && l < 0.5)
    return { label: "Flash Trend", color: "#EAB308" };
  if (v < 0.3 && l >= 0.7)
    return { label: "Steady Presence", color: "#3B82F6" };
  if (d >= 0.7 && s >= 0.7)
    return { label: "Niche Opportunity", color: "#F97316" };
  if (v >= 0.5 && s >= 0.5)
    return { label: "White Space", color: "#22C55E" };
  if (d >= 0.7 && s < 0.3)
    return { label: "Oversaturated", color: "#EF4444" };
  return { label: "Monitor", color: "#9CA3AF" };
}

function TopicCard({
  topicName,
  velocity,
  longevity,
  density,
  scarcity,
  postCount,
  alerts,
  avgEmpathy,
  topEmotions,
}: {
  topicName: string;
  velocity: number;
  longevity: number;
  density: number;
  scarcity: number;
  postCount: number;
  alerts: { severity: string; title: string }[];
  avgEmpathy: number | null;
  topEmotions: { emotion: string; count: number }[];
}) {
  const { label: strategicLabel, color: labelColor } = getStrategicLabel(
    velocity,
    longevity,
    density,
    scarcity
  );

  const dataSummary = `Topic: ${topicName} (${postCount} posts), Velocity: ${velocity.toFixed(2)}, Longevity: ${longevity.toFixed(2)}, Density: ${density.toFixed(2)}, Scarcity: ${scarcity.toFixed(2)}, Strategy: ${strategicLabel}`;

  return (
    <div className="rounded border border-border p-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-sm font-semibold">{topicName}</div>
        <Badge
          style={{ backgroundColor: labelColor, color: "#fff" }}
          className="text-[10px]"
        >
          {strategicLabel}
        </Badge>
      </div>

      {/* VLDS metrics */}
      <div className="mb-2 grid grid-cols-4 gap-2 text-center text-xs">
        {[
          { label: "Velocity", value: velocity },
          { label: "Longevity", value: longevity },
          { label: "Density", value: density },
          { label: "Scarcity", value: scarcity },
        ].map((m) => (
          <div key={m.label}>
            <div className="text-muted-foreground">{m.label}</div>
            <div className="font-semibold">
              {Math.round(m.value * 100)}%
            </div>
          </div>
        ))}
      </div>

      {/* Post count */}
      <div className="mb-2 text-xs text-muted-foreground">
        {postCount} posts analyzed
      </div>

      {/* Empathy + top emotions */}
      {avgEmpathy !== null && (
        <div className="mb-2 text-xs text-muted-foreground">
          Avg empathy: {Math.round(avgEmpathy)}/100
        </div>
      )}
      {topEmotions.length > 0 && (
        <div className="mb-2 text-xs text-muted-foreground">
          Top emotions: {topEmotions.map((e) => `${e.emotion} (${e.count})`).join(", ")}
        </div>
      )}

      {/* Recent alerts */}
      {alerts.length > 0 && (
        <div className="mb-2 space-y-0.5">
          <div className="text-xs text-muted-foreground">Recent Alerts:</div>
          {alerts.slice(0, 5).map((a, i) => (
            <div key={i} className="text-xs">
              {SEVERITY_ICONS[a.severity] ?? "\uD83D\uDD35"} {a.title}
            </div>
          ))}
        </div>
      )}

      <HelperButton chartType="topic_intelligence" dataSummary={dataSummary} />
    </div>
  );
}

export function TopicIntelligence() {
  const { username } = useAuth();
  const { data: vldsData, isLoading: vldsLoading } = useTopicVLDS();
  const { data: topicWatchlist } = useTopics(username);
  const { data: alertsData } = useAlerts(username, 7);
  const { data: combinedData } = useCombinedData(7);

  if (vldsLoading) {
    return (
      <div>
        <h2 className="mb-1 text-lg font-semibold">Topic Intelligence</h2>
        <CardListSkeleton count={4} />
      </div>
    );
  }

  // Build per-topic VLDS map from separate arrays
  const topicMap = new Map<
    string,
    {
      velocity: number;
      longevity: number;
      density: number;
      scarcity: number;
      postCount: number;
    }
  >();

  for (const item of vldsData?.topic_longevity ?? []) {
    const key = (item.topic ?? "").toLowerCase();
    const existing = topicMap.get(key) || {
      velocity: 0,
      longevity: 0,
      density: 0,
      scarcity: 0,
      postCount: 0,
    };
    existing.velocity = item.velocity_score ?? 0;
    existing.longevity = item.longevity_score ?? 0;
    existing.postCount = item.post_count ?? 0;
    topicMap.set(key, existing);
  }
  for (const item of vldsData?.topic_density ?? []) {
    const key = (item.topic ?? "").toLowerCase();
    const existing = topicMap.get(key) || {
      velocity: 0,
      longevity: 0,
      density: 0,
      scarcity: 0,
      postCount: 0,
    };
    existing.density = item.density_score ?? 0;
    topicMap.set(key, existing);
  }
  for (const item of vldsData?.topic_scarcity ?? []) {
    const key = (item.topic ?? "").toLowerCase();
    const existing = topicMap.get(key) || {
      velocity: 0,
      longevity: 0,
      density: 0,
      scarcity: 0,
      postCount: 0,
    };
    existing.scarcity = item.scarcity_score ?? 0;
    topicMap.set(key, existing);
  }

  // Build per-topic alert lists
  const allAlerts = alertsData?.data ?? [];
  const topicAlerts = new Map<string, { severity: string; title: string }[]>();
  for (const a of allAlerts) {
    const t = (a.topic ?? "").toLowerCase();
    if (!t) continue;
    if (!topicAlerts.has(t)) topicAlerts.set(t, []);
    topicAlerts.get(t)!.push({ severity: a.severity, title: a.title });
  }

  // Per-topic empathy and emotions from combined data
  const topicEmpathy = new Map<string, number[]>();
  const topicEmotions = new Map<string, Map<string, number>>();
  for (const item of combinedData?.data ?? []) {
    const t = (item.topic ?? "").toLowerCase();
    if (!t) continue;
    // Empathy
    if (item.empathy_score != null) {
      if (!topicEmpathy.has(t)) topicEmpathy.set(t, []);
      topicEmpathy.get(t)!.push(item.empathy_score);
    }
    // Emotions
    const emo = item.emotion_top_1;
    if (emo) {
      if (!topicEmotions.has(t)) topicEmotions.set(t, new Map());
      const emoMap = topicEmotions.get(t)!;
      emoMap.set(emo, (emoMap.get(emo) || 0) + 1);
    }
  }

  // Filter to only watchlist topics
  const watchlistTopics = new Set(
    (topicWatchlist?.topics ?? []).map((t) => t.topic_name.toLowerCase())
  );

  const topics = Array.from(topicMap.entries())
    .filter(([key]) => watchlistTopics.size === 0 || watchlistTopics.has(key))
    .sort(([, a], [, b]) => b.velocity - a.velocity);

  return (
    <div>
      <h2 className="mb-1 text-lg font-semibold">Topic Intelligence</h2>
      <p className="mb-3 text-xs text-muted-foreground">
        VLDS metrics and alerts for your watched topics.
      </p>

      {topics.length === 0 ? (
        <p className="py-4 text-center text-sm text-muted-foreground">
          No topic data available.
        </p>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {topics.map(([key, scores]) => {
            const empScores = topicEmpathy.get(key);
            const avgEmp = empScores && empScores.length > 0
              ? normalizeEmpathyScore(empScores.reduce((a, b) => a + b, 0) / empScores.length)
              : null;
            const emoMap = topicEmotions.get(key);
            const topEmo = emoMap
              ? Array.from(emoMap.entries())
                  .sort((a, b) => b[1] - a[1])
                  .slice(0, 3)
                  .map(([emotion, count]) => ({ emotion, count }))
              : [];
            return (
              <TopicCard
                key={key}
                topicName={key}
                velocity={scores.velocity}
                longevity={scores.longevity}
                density={scores.density}
                scarcity={scores.scarcity}
                postCount={scores.postCount}
                alerts={topicAlerts.get(key) ?? []}
                avgEmpathy={avgEmp}
                topEmotions={topEmo}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
