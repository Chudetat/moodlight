"use client";

import { useState } from "react";
import { useTopicVLDS, useAlerts } from "@/lib/hooks/use-api";
import { useAuth } from "@/lib/hooks/use-auth";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronUp } from "lucide-react";
import { HelperButton } from "@/components/shared/helper-button";
import { CardListSkeleton } from "@/components/shared/loading-skeleton";

function getStrategicLabel(v: number, l: number, d: number, s: number): string {
  if (v > 0.6 && l > 0.5 && d < 0.4 && s > 0.5) return "First Mover";
  if (v > 0.6 && l < 0.3) return "Flash Trend";
  if (d > 0.6 && s < 0.3) return "Red Ocean";
  if (d > 0.5 && s > 0.5) return "Niche Opportunity";
  if (l > 0.7) return "Established";
  return "Emerging";
}

function getLabelColor(label: string): string {
  switch (label) {
    case "First Mover": return "text-green-400";
    case "Flash Trend": return "text-yellow-400";
    case "Red Ocean": return "text-red-400";
    case "Niche Opportunity": return "text-blue-400";
    case "Established": return "text-purple-400";
    default: return "text-muted-foreground";
  }
}

interface TopicCardProps {
  topic: string;
  velocity: number;
  longevity: number;
  density: number;
  scarcity: number;
  alertCount: number;
}

function TopicCard({
  topic,
  velocity,
  longevity,
  density,
  scarcity,
  alertCount,
}: TopicCardProps) {
  const [expanded, setExpanded] = useState(false);
  const label = getStrategicLabel(velocity, longevity, density, scarcity);

  const dataSummary = `Topic: ${topic}\nVelocity: ${velocity.toFixed(2)}\nLongevity: ${longevity.toFixed(2)}\nDensity: ${density.toFixed(2)}\nScarcity: ${scarcity.toFixed(2)}\nStrategic Label: ${label}`;

  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium capitalize">{topic}</span>
            <Badge variant="secondary" className={`text-[10px] ${getLabelColor(label)}`}>
              {label}
            </Badge>
            {alertCount > 0 && (
              <Badge variant="outline" className="text-[10px]">
                {alertCount} alert{alertCount !== 1 ? "s" : ""}
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-1">
            <HelperButton chartType="topic_intelligence" dataSummary={dataSummary} />
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? (
                <ChevronUp className="h-3.5 w-3.5" />
              ) : (
                <ChevronDown className="h-3.5 w-3.5" />
              )}
            </Button>
          </div>
        </div>

        {expanded && (
          <div className="mt-3 grid grid-cols-4 gap-3 border-t border-border pt-3">
            {[
              { name: "Velocity", val: velocity },
              { name: "Longevity", val: longevity },
              { name: "Density", val: density },
              { name: "Scarcity", val: scarcity },
            ].map((m) => (
              <div key={m.name} className="text-center">
                <p className="text-[10px] text-muted-foreground">{m.name}</p>
                <p className="text-sm font-bold tabular-nums">
                  {m.val.toFixed(2)}
                </p>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function TopicIntelligence() {
  const { username } = useAuth();
  const { data: vldsData, isLoading: vldsLoading } = useTopicVLDS();
  const { data: alertsData } = useAlerts(username, 7);

  if (vldsLoading) {
    return (
      <div>
        <h2 className="mb-3 text-lg font-semibold">Topic Intelligence</h2>
        <CardListSkeleton count={4} />
      </div>
    );
  }

  // Build per-topic VLDS map from separate arrays
  const topicMap = new Map<
    string,
    { velocity: number; longevity: number; density: number; scarcity: number }
  >();

  for (const item of vldsData?.topic_longevity ?? []) {
    const existing = topicMap.get(item.scope_name) || {
      velocity: 0,
      longevity: 0,
      density: 0,
      scarcity: 0,
    };
    existing.longevity = item.metric_value;
    topicMap.set(item.scope_name, existing);
  }
  for (const item of vldsData?.topic_density ?? []) {
    const existing = topicMap.get(item.scope_name) || {
      velocity: 0,
      longevity: 0,
      density: 0,
      scarcity: 0,
    };
    existing.density = item.metric_value;
    topicMap.set(item.scope_name, existing);
  }
  for (const item of vldsData?.topic_scarcity ?? []) {
    const existing = topicMap.get(item.scope_name) || {
      velocity: 0,
      longevity: 0,
      density: 0,
      scarcity: 0,
    };
    existing.scarcity = item.metric_value;
    topicMap.set(item.scope_name, existing);
  }

  // Count alerts per topic
  const alertsByTopic = new Map<string, number>();
  for (const alert of alertsData?.data ?? []) {
    if (alert.topic) {
      alertsByTopic.set(
        alert.topic,
        (alertsByTopic.get(alert.topic) || 0) + 1
      );
    }
  }

  const topics = Array.from(topicMap.entries()).sort(
    ([, a], [, b]) => b.velocity - a.velocity
  );

  return (
    <div>
      <h2 className="mb-3 text-lg font-semibold">Topic Intelligence</h2>
      <div className="space-y-2">
        {topics.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">
            No topic data available.
          </p>
        ) : (
          topics.map(([topic, scores]) => (
            <TopicCard
              key={topic}
              topic={topic}
              {...scores}
              alertCount={alertsByTopic.get(topic) || 0}
            />
          ))
        )}
      </div>
    </div>
  );
}
