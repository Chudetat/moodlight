"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Button } from "@/components/ui/button";
import { X } from "lucide-react";

interface TourStep {
  targetId: string;
  title: string;
  description: string;
}

const TOUR_STEPS: TourStep[] = [
  {
    targetId: "section-cultural-pulse",
    title: "Cultural Pulse",
    description:
      "Your real-time overview. Empathy scores, threat levels, and emotion breakdowns update hourly as new data flows in.",
  },
  {
    targetId: "section-market-sentiment",
    title: "Market Sentiment",
    description:
      "Live market indices, brand stock prices, and economic indicators at a glance. Red and green circles show market direction.",
  },
  {
    targetId: "section-intelligence-alerts",
    title: "Intelligence Alerts",
    description:
      "Moodlight automatically detects anomalies, emerging trends, and market-mood divergences. Each alert includes AI-powered reasoning.",
  },
  {
    targetId: "section-competitive-war-room",
    title: "Competitive War Room",
    description:
      "Track competitors side-by-side. Share of voice, VLDS scores, and strategic gap analysis — updated automatically.",
  },
  {
    targetId: "section-ask-moodlight",
    title: "Ask Moodlight",
    description:
      "Ask any question about your brands, topics, or market conditions. Powered by AI with access to all your real-time data.",
  },
  {
    targetId: "sidebar-watchlists",
    title: "Your Watchlists",
    description:
      "Add brands and topics here to personalize your dashboard. Everything you see is filtered through your watchlist.",
  },
];

const TOUR_STORAGE_KEY = "moodlight-tour-completed";

export function GuidedTour() {
  const [step, setStep] = useState(-1);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const rafRef = useRef(0);

  const isActive = step >= 0 && step < TOUR_STEPS.length;

  // Start tour on first visit
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (localStorage.getItem(TOUR_STORAGE_KEY)) return;
    const timer = setTimeout(() => setStep(0), 2000);
    return () => clearTimeout(timer);
  }, []);

  // Track target element rect continuously while tour is active
  const updateRect = useCallback(() => {
    if (step < 0 || step >= TOUR_STEPS.length) return;
    const el = document.getElementById(TOUR_STEPS[step].targetId);
    if (el) {
      setRect(el.getBoundingClientRect());
    } else {
      setRect(null);
    }
    rafRef.current = requestAnimationFrame(updateRect);
  }, [step]);

  useEffect(() => {
    if (!isActive) return;
    rafRef.current = requestAnimationFrame(updateRect);
    return () => cancelAnimationFrame(rafRef.current);
  }, [isActive, updateRect]);

  // Scroll to target when step changes
  useEffect(() => {
    if (!isActive) return;
    const el = document.getElementById(TOUR_STEPS[step].targetId);
    if (!el) {
      // Skip missing elements
      if (step < TOUR_STEPS.length - 1) {
        setStep((s) => s + 1);
      } else {
        finish();
      }
      return;
    }

    // Force contentVisibility to visible so the element renders
    el.style.contentVisibility = "visible";

    // Small delay then scroll
    setTimeout(() => {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 100);
  }, [step, isActive]);

  const finish = useCallback(() => {
    setStep(-1);
    setRect(null);
    localStorage.setItem(TOUR_STORAGE_KEY, "true");
  }, []);

  const next = useCallback(() => {
    if (step >= TOUR_STEPS.length - 1) {
      finish();
    } else {
      setStep((s) => s + 1);
    }
  }, [step, finish]);

  if (!isActive || !rect) return null;

  const current = TOUR_STEPS[step];
  const tooltipWidth = 340;
  const gap = 16;

  // Decide tooltip position: below if target is in top half, above if bottom half
  const targetCenterY = rect.top + rect.height / 2;
  const viewH = window.innerHeight;
  const placeBelow = targetCenterY < viewH * 0.5;

  let tooltipTop: number;
  if (placeBelow) {
    tooltipTop = rect.bottom + gap;
  } else {
    tooltipTop = rect.top - gap;
  }

  // Center horizontally on the target, clamped to viewport
  let tooltipLeft = rect.left + rect.width / 2 - tooltipWidth / 2;
  tooltipLeft = Math.max(16, Math.min(tooltipLeft, window.innerWidth - tooltipWidth - 16));

  return (
    <>
      {/* Dark overlay with spotlight cutout — uses CSS box-shadow trick */}
      <div
        className="fixed inset-0 z-[10000]"
        onClick={finish}
        style={{ pointerEvents: "auto" }}
      >
        {/* Full-screen dark layer with a transparent hole */}
        <div
          className="fixed z-[10000]"
          style={{
            top: rect.top - 8,
            left: rect.left - 8,
            width: rect.width + 16,
            height: rect.height + 16,
            borderRadius: 8,
            boxShadow: "0 0 0 9999px rgba(0,0,0,0.6)",
            pointerEvents: "none",
          }}
        />
      </div>

      {/* Spotlight border */}
      <div
        className="pointer-events-none fixed z-[10001] rounded-lg ring-2 ring-primary"
        style={{
          top: rect.top - 8,
          left: rect.left - 8,
          width: rect.width + 16,
          height: rect.height + 16,
        }}
      />

      {/* Tooltip */}
      <div
        className="fixed z-[10002] rounded-lg border border-border bg-card p-4 shadow-xl"
        style={{
          top: placeBelow ? tooltipTop : undefined,
          bottom: placeBelow ? undefined : viewH - tooltipTop,
          left: tooltipLeft,
          width: tooltipWidth,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={finish}
          className="absolute right-2 top-2 text-muted-foreground hover:text-foreground"
        >
          <X className="h-4 w-4" />
        </button>

        <p className="text-sm font-semibold">{current.title}</p>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          {current.description}
        </p>

        <div className="mt-3 flex items-center justify-between">
          <span className="text-[10px] text-muted-foreground">
            {step + 1} of {TOUR_STEPS.length}
          </span>
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={finish}>
              Skip tour
            </Button>
            <Button size="sm" className="h-7 text-xs" onClick={next}>
              {step >= TOUR_STEPS.length - 1 ? "Done" : "Next"}
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
