"use client";

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { X } from "lucide-react";

interface TourStep {
  targetId: string;
  title: string;
  description: string;
  position: "bottom" | "top" | "left" | "right";
}

const TOUR_STEPS: TourStep[] = [
  {
    targetId: "section-cultural-pulse",
    title: "Cultural Pulse",
    description:
      "Your real-time overview. Empathy scores, threat levels, and emotion breakdowns update hourly as new data flows in.",
    position: "bottom",
  },
  {
    targetId: "section-market-sentiment",
    title: "Market Sentiment",
    description:
      "Live market indices, brand stock prices, and economic indicators at a glance. Red and green circles show market direction.",
    position: "bottom",
  },
  {
    targetId: "section-intelligence-alerts",
    title: "Intelligence Alerts",
    description:
      "Moodlight automatically detects anomalies, emerging trends, and market-mood divergences. Each alert includes AI-powered reasoning.",
    position: "top",
  },
  {
    targetId: "section-competitive-war-room",
    title: "Competitive War Room",
    description:
      "Track competitors side-by-side. Share of voice, VLDS scores, and strategic gap analysis — updated automatically.",
    position: "top",
  },
  {
    targetId: "section-ask-moodlight",
    title: "Ask Moodlight",
    description:
      "Ask any question about your brands, topics, or market conditions. Powered by AI with access to all your real-time data.",
    position: "top",
  },
  {
    targetId: "sidebar-watchlists",
    title: "Your Watchlists",
    description:
      "Add brands and topics here to personalize your dashboard. Everything you see is filtered through your watchlist.",
    position: "right",
  },
];

const TOUR_STORAGE_KEY = "moodlight-tour-completed";

export function GuidedTour() {
  const [currentStep, setCurrentStep] = useState(-1);
  const [tooltipStyle, setTooltipStyle] = useState<React.CSSProperties>({});
  const [arrowStyle, setArrowStyle] = useState<React.CSSProperties>({});
  const [arrowDirection, setArrowDirection] = useState<string>("top");

  const isActive = currentStep >= 0 && currentStep < TOUR_STEPS.length;

  useEffect(() => {
    if (localStorage.getItem(TOUR_STORAGE_KEY)) return;
    // Delay start so dashboard has time to render
    const timer = setTimeout(() => setCurrentStep(0), 1500);
    return () => clearTimeout(timer);
  }, []);

  const positionTooltip = useCallback(() => {
    if (!isActive) return;
    const step = TOUR_STEPS[currentStep];
    const el = document.getElementById(step.targetId);
    if (!el) return;

    const rect = el.getBoundingClientRect();
    const tooltipWidth = 340;
    const tooltipGap = 16;

    let top = 0;
    let left = 0;
    let arrow: React.CSSProperties = {};
    let dir = "top";

    switch (step.position) {
      case "bottom":
        top = rect.bottom + tooltipGap + window.scrollY;
        left = rect.left + rect.width / 2 - tooltipWidth / 2;
        arrow = { top: -8, left: tooltipWidth / 2 - 8 };
        dir = "top";
        break;
      case "top":
        top = rect.top - tooltipGap + window.scrollY;
        left = rect.left + rect.width / 2 - tooltipWidth / 2;
        arrow = { bottom: -8, left: tooltipWidth / 2 - 8 };
        dir = "bottom";
        break;
      case "right":
        top = rect.top + rect.height / 2 + window.scrollY;
        left = rect.right + tooltipGap;
        arrow = { top: 20, left: -8 };
        dir = "left";
        break;
      case "left":
        top = rect.top + rect.height / 2 + window.scrollY;
        left = rect.left - tooltipWidth - tooltipGap;
        arrow = { top: 20, right: -8 };
        dir = "right";
        break;
    }

    // Keep tooltip on screen
    left = Math.max(16, Math.min(left, window.innerWidth - tooltipWidth - 16));

    setTooltipStyle({
      position: "absolute",
      top,
      left,
      width: tooltipWidth,
      zIndex: 10001,
      transform: step.position === "top" ? "translateY(-100%)" : undefined,
    });
    setArrowStyle(arrow);
    setArrowDirection(dir);
  }, [currentStep, isActive]);

  useEffect(() => {
    if (!isActive) return;

    const step = TOUR_STEPS[currentStep];
    const el = document.getElementById(step.targetId);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      // Position after scroll settles
      const timer = setTimeout(positionTooltip, 400);
      return () => clearTimeout(timer);
    }
  }, [currentStep, isActive, positionTooltip]);

  useEffect(() => {
    if (!isActive) return;
    window.addEventListener("resize", positionTooltip);
    return () => window.removeEventListener("resize", positionTooltip);
  }, [isActive, positionTooltip]);

  const finish = useCallback(() => {
    setCurrentStep(-1);
    localStorage.setItem(TOUR_STORAGE_KEY, "true");
  }, []);

  const next = useCallback(() => {
    if (currentStep >= TOUR_STEPS.length - 1) {
      finish();
    } else {
      setCurrentStep((s) => s + 1);
    }
  }, [currentStep, finish]);

  if (!isActive) return null;

  const step = TOUR_STEPS[currentStep];
  const targetEl = typeof document !== "undefined" ? document.getElementById(step.targetId) : null;
  const targetRect = targetEl?.getBoundingClientRect();

  const arrowBorderMap: Record<string, string> = {
    top: "border-l-8 border-r-8 border-b-8 border-l-transparent border-r-transparent border-b-border",
    bottom: "border-l-8 border-r-8 border-t-8 border-l-transparent border-r-transparent border-t-border",
    left: "border-t-8 border-b-8 border-r-8 border-t-transparent border-b-transparent border-r-border",
    right: "border-t-8 border-b-8 border-l-8 border-t-transparent border-b-transparent border-l-border",
  };

  return (
    <>
      {/* Overlay with spotlight cutout */}
      <div className="fixed inset-0 z-[10000]" onClick={finish}>
        <svg className="h-full w-full" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <mask id="tour-spotlight">
              <rect x="0" y="0" width="100%" height="100%" fill="white" />
              {targetRect && (
                <rect
                  x={targetRect.left - 8}
                  y={targetRect.top - 8}
                  width={targetRect.width + 16}
                  height={targetRect.height + 16}
                  rx="8"
                  fill="black"
                />
              )}
            </mask>
          </defs>
          <rect
            x="0"
            y="0"
            width="100%"
            height="100%"
            fill="rgba(0,0,0,0.6)"
            mask="url(#tour-spotlight)"
          />
        </svg>
      </div>

      {/* Spotlight border highlight */}
      {targetRect && (
        <div
          className="pointer-events-none fixed z-[10001] rounded-lg ring-2 ring-primary"
          style={{
            top: targetRect.top - 8,
            left: targetRect.left - 8,
            width: targetRect.width + 16,
            height: targetRect.height + 16,
          }}
        />
      )}

      {/* Tooltip */}
      <div
        style={tooltipStyle}
        className="rounded-lg border border-border bg-card p-4 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Arrow */}
        <div
          className={`absolute h-0 w-0 ${arrowBorderMap[arrowDirection] || ""}`}
          style={arrowStyle}
        />

        {/* Close button */}
        <button
          onClick={finish}
          className="absolute right-2 top-2 text-muted-foreground hover:text-foreground"
        >
          <X className="h-4 w-4" />
        </button>

        <p className="text-sm font-semibold">{step.title}</p>
        <p className="mt-1 text-xs text-muted-foreground">{step.description}</p>

        <div className="mt-3 flex items-center justify-between">
          <span className="text-[10px] text-muted-foreground">
            {currentStep + 1} of {TOUR_STEPS.length}
          </span>
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={finish}>
              Skip tour
            </Button>
            <Button size="sm" className="h-7 text-xs" onClick={next}>
              {currentStep >= TOUR_STEPS.length - 1 ? "Done" : "Next"}
            </Button>
          </div>
        </div>
      </div>
    </>
  );
}

export function restartTour() {
  localStorage.removeItem(TOUR_STORAGE_KEY);
  window.location.reload();
}
