"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronUp, ThumbsUp, ThumbsDown } from "lucide-react";
import { SEVERITY_ICONS } from "@/lib/constants";
import { timeAgo } from "@/lib/utils";
import { useAlertFeedback } from "@/lib/hooks/use-api";
import type { Alert } from "@/lib/types";

interface AlertCardProps {
  alert: Alert;
}

export function AlertCard({ alert }: AlertCardProps) {
  const [expanded, setExpanded] = useState(false);
  const feedback = useAlertFeedback();

  const icon = SEVERITY_ICONS[alert.severity] || "\uD83D\uDD35";

  function handleExpand() {
    if (!expanded) {
      feedback.mutate({ alertId: alert.id, action: "expanded" });
    }
    setExpanded(!expanded);
  }

  // Parse investigation JSON (contains analysis, confidence, recommendation)
  let confidence: number | undefined;
  let recommendation: string | undefined;
  let analysis: string | undefined;
  if (alert.investigation) {
    try {
      const parsed = JSON.parse(alert.investigation);
      confidence = parsed.overall_confidence;
      recommendation = parsed.recommendation;
      analysis = parsed.analysis;
    } catch {
      // investigation is plain text
      analysis = alert.investigation;
    }
  }

  // Extract reasoning steps from analysis text
  const reasoningSteps: string[] = [];
  if (analysis) {
    // Split analysis into meaningful sections
    const lines = analysis.split("\n").filter((l: string) => l.trim());
    for (const line of lines) {
      if (line.trim()) reasoningSteps.push(line.trim());
    }
  }

  return (
    <Card
      className={`transition-colors ${
        alert.is_read ? "opacity-70" : ""
      }`}
    >
      <CardContent className="p-4">
        {/* Header row */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-start gap-2">
            <span className="mt-0.5 text-base">{icon}</span>
            <div className="min-w-0">
              <p className="text-sm font-medium leading-tight">
                {alert.title}
              </p>
              <div className="mt-1 flex flex-wrap items-center gap-1.5">
                <Badge variant="secondary" className="text-[10px]">
                  {alert.alert_type.replace(/_/g, " ")}
                </Badge>
                {alert.brand && (
                  <Badge variant="outline" className="text-[10px]">
                    {alert.brand}
                  </Badge>
                )}
                {alert.topic && (
                  <Badge variant="outline" className="text-[10px]">
                    {alert.topic}
                  </Badge>
                )}
                <span className="text-[10px] text-muted-foreground">
                  {timeAgo(alert.timestamp)}
                </span>
              </div>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={handleExpand}
          >
            {expanded ? (
              <ChevronUp className="h-3.5 w-3.5" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5" />
            )}
          </Button>
        </div>

        {/* Summary */}
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
          {alert.summary}
        </p>

        {/* Expanded content */}
        {expanded && (
          <div className="mt-3 space-y-3 border-t border-border pt-3">
            {/* Confidence */}
            {confidence !== undefined && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">
                  Confidence:
                </span>
                <div className="h-1.5 w-24 rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{ width: `${confidence}%` }}
                  />
                </div>
                <span className="text-xs font-medium">{confidence}%</span>
              </div>
            )}

            {/* Analysis */}
            {analysis && (
              <div>
                <p className="mb-1.5 text-xs font-medium">Analysis</p>
                <p className="whitespace-pre-wrap text-xs text-muted-foreground">
                  {analysis}
                </p>
              </div>
            )}

            {/* Recommendation */}
            {recommendation && (
              <div>
                <p className="mb-1 text-xs font-medium">Recommendation</p>
                <p className="text-xs text-muted-foreground capitalize">
                  {recommendation.replace(/_/g, " ")}
                </p>
              </div>
            )}

            {/* Feedback buttons */}
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="icon-xs"
                onClick={() =>
                  feedback.mutate({
                    alertId: alert.id,
                    action: "thumbs_up",
                  })
                }
                title="Helpful"
              >
                <ThumbsUp className="h-3 w-3" />
              </Button>
              <Button
                variant="ghost"
                size="icon-xs"
                onClick={() =>
                  feedback.mutate({
                    alertId: alert.id,
                    action: "thumbs_down",
                  })
                }
                title="Not helpful"
              >
                <ThumbsDown className="h-3 w-3" />
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
