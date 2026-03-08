"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SEVERITY_ICONS } from "@/lib/constants";
import { timeAgo } from "@/lib/utils";
import { useAlertFeedback, useMarkAlertRead } from "@/lib/hooks/use-api";
import type { Alert, Investigation } from "@/lib/types";

function parseInvestigation(raw: Alert["investigation"]): Investigation | null {
  if (!raw) return null;
  if (typeof raw === "object") return raw as Investigation;
  try {
    return JSON.parse(raw) as Investigation;
  } catch {
    return null;
  }
}

function parseData(raw: Alert["data"]): Record<string, unknown> | null {
  if (!raw) return null;
  if (typeof raw === "object") return raw;
  try {
    return JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return null;
  }
}

interface AlertCardProps {
  alert: Alert;
}

export function AlertCard({ alert }: AlertCardProps) {
  const [expanded, setExpanded] = useState(false);
  const markRead = useMarkAlertRead();
  const feedback = useAlertFeedback();

  const icon =
    alert.alert_type === "situation_report"
      ? "\uD83D\uDD17"
      : (SEVERITY_ICONS[alert.severity] ?? "\uD83D\uDD35");

  const investigation = parseInvestigation(alert.investigation);
  const alertData = parseData(alert.data);

  const handleExpand = () => {
    if (!expanded && !alert.is_read) {
      markRead.mutate(alert.id);
    }
    setExpanded(!expanded);
  };

  return (
    <div
      className={`rounded border border-border p-3 ${
        alert.is_read ? "opacity-70" : ""
      }`}
    >
      {/* Header */}
      <button
        className="flex w-full items-start gap-2 text-left"
        onClick={handleExpand}
      >
        <span className="mt-0.5 text-base">{icon}</span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            {(alert.brand_name || alert.brand) && (
              <Badge variant="outline" className="px-1 py-0 text-[10px]">
                {alert.brand_name || alert.brand}
              </Badge>
            )}
            {alert.topic && (
              <Badge variant="secondary" className="px-1 py-0 text-[10px]">
                {alert.topic}
              </Badge>
            )}
            <Badge
              variant="outline"
              className="px-1 py-0 text-[10px] text-muted-foreground"
            >
              {alert.alert_type.replace(/_/g, " ")}
            </Badge>
          </div>
          <div className="mt-0.5 text-sm font-medium">{alert.title}</div>
        </div>
        <span className="shrink-0 text-xs text-muted-foreground">
          {timeAgo(alert.timestamp)}
        </span>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="mt-3 space-y-3 border-t border-border/50 pt-3">
          <p className="text-sm">{alert.description || alert.summary}</p>

          {(alert.recommendation || investigation?.recommendation) && (
            <div className="rounded bg-muted p-2 text-sm">
              <span className="font-medium">Recommendation: </span>
              {(
                alert.recommendation ||
                investigation?.recommendation ||
                ""
              ).replace(/_/g, " ")}
            </div>
          )}

          {/* Situation report: correlated alerts */}
          {alert.alert_type === "situation_report" && alertData && (
            <div className="space-y-1">
              <div className="text-xs font-medium text-muted-foreground">
                Correlated Signals:
              </div>
              {(
                (alertData.correlated_alerts as
                  | {
                      severity?: string;
                      alert_type?: string;
                      title?: string;
                    }[]
                  | undefined) ?? []
              ).map(
                (
                  ca: {
                    severity?: string;
                    alert_type?: string;
                    title?: string;
                  },
                  i: number
                ) => (
                  <div key={i} className="text-xs">
                    {SEVERITY_ICONS[ca.severity ?? "info"] ?? "\uD83D\uDD35"}{" "}
                    <span className="font-medium">
                      {(ca.alert_type ?? "")
                        .replace(/_/g, " ")
                        .replace(/\b\w/g, (c) => c.toUpperCase())}
                      :
                    </span>{" "}
                    {ca.title ?? "Untitled"}
                  </div>
                )
              )}
            </div>
          )}

          {/* Investigation (reasoning chain) */}
          {investigation &&
            investigation.steps &&
            investigation.steps.length > 0 && (
              <div className="space-y-2">
                <div className="text-xs font-medium text-muted-foreground">
                  Investigation (
                  {investigation.overall_confidence ??
                    investigation.final_confidence ??
                    alert.confidence ??
                    0}
                  /100 confidence)
                </div>
                {investigation.steps.map((step, idx) => {
                  const stepTitle =
                    step.title ?? step.question ?? `Step ${step.step}`;
                  const stepContent = step.content ?? step.finding ?? "";
                  const confPct =
                    typeof step.confidence === "number"
                      ? step.confidence <= 1
                        ? Math.round(step.confidence * 100)
                        : Math.round(step.confidence)
                      : 0;
                  return (
                    <div
                      key={idx}
                      className="rounded border border-border/50 p-2 text-xs"
                    >
                      <div className="font-medium">
                        {stepTitle} (confidence: {confPct}%)
                      </div>
                      {stepContent && (
                        <div className="mt-1 whitespace-pre-wrap text-muted-foreground">
                          {stepContent}
                        </div>
                      )}
                      {step.likely_causes && step.likely_causes.length > 0 && (
                        <div className="mt-1">
                          <span className="font-medium">Likely causes: </span>
                          {step.likely_causes.join(", ")}
                        </div>
                      )}
                      {step.recommended_actions &&
                        step.recommended_actions.length > 0 && (
                          <div className="mt-1">
                            <span className="font-medium">Recommended: </span>
                            {step.recommended_actions.join(", ")}
                          </div>
                        )}
                      {step.frameworks_applied &&
                        step.frameworks_applied.length > 0 && (
                          <div className="mt-1 text-muted-foreground">
                            Frameworks: {step.frameworks_applied.join(", ")}
                          </div>
                        )}
                    </div>
                  );
                })}
              </div>
            )}

          {/* Feedback */}
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              className="text-xs"
              onClick={() =>
                feedback.mutate({ alertId: alert.id, action: "thumbs_up" })
              }
            >
              👍 Helpful
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="text-xs"
              onClick={() =>
                feedback.mutate({ alertId: alert.id, action: "thumbs_down" })
              }
            >
              👎 Not helpful
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
