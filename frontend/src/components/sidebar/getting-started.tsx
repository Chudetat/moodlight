"use client";

import { useState } from "react";
import { useAuth } from "@/lib/hooks/use-auth";
import { useBrands, useTopics } from "@/lib/hooks/use-api";
import { restartTour } from "@/components/onboarding/guided-tour";

export function GettingStarted() {
  const { username } = useAuth();
  const { data: brandData } = useBrands(username);
  const { data: topicData } = useTopics(username);
  const [dismissed, setDismissed] = useState(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem("onboarding_dismissed") === "true";
  });

  if (dismissed) return null;

  const hasBrands = (brandData?.brands?.length ?? 0) > 0;
  const hasTopics = (topicData?.topics?.length ?? 0) > 0;
  const hasReport =
    typeof window !== "undefined" &&
    localStorage.getItem("onboarding_report") === "true";
  const hasChat =
    typeof window !== "undefined" &&
    localStorage.getItem("onboarding_chat") === "true";
  const done = [hasBrands, hasTopics, hasReport, hasChat].filter(Boolean).length;

  if (done >= 4) {
    return (
      <div>
        <button
          className="text-xs text-muted-foreground hover:text-foreground"
          onClick={restartTour}
        >
          Take the guided tour
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium uppercase text-muted-foreground">
          Getting Started ({done}/4)
        </p>
        <button
          className="text-xs text-muted-foreground hover:text-foreground"
          onClick={() => {
            setDismissed(true);
            localStorage.setItem("onboarding_dismissed", "true");
          }}
        >
          Dismiss
        </button>
      </div>
      <button
        className="text-xs text-primary hover:underline"
        onClick={restartTour}
      >
        Take the guided tour
      </button>
      <div className="space-y-1 text-sm">
        <div className="flex items-center gap-2">
          <span>{hasBrands ? "\u2705" : "\u2B1C"}</span>
          <span
            className={
              hasBrands ? "text-muted-foreground line-through" : ""
            }
          >
            Add a brand to watch
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span>{hasTopics ? "\u2705" : "\u2B1C"}</span>
          <span
            className={
              hasTopics ? "text-muted-foreground line-through" : ""
            }
          >
            Add a topic to monitor
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span>{hasReport ? "\u2705" : "\u2B1C"}</span>
          <span
            className={
              hasReport ? "text-muted-foreground line-through" : ""
            }
          >
            Generate an intelligence report
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span>{hasChat ? "\u2705" : "\u2B1C"}</span>
          <span
            className={hasChat ? "text-muted-foreground line-through" : ""}
          >
            Ask Moodlight a question
          </span>
        </div>
      </div>
    </div>
  );
}
