"use client";

import { memo } from "react";
import { cn } from "@/lib/utils";

interface MetricCardProps {
  label: React.ReactNode;
  value: string | number;
  delta?: string;
  deltaColor?: "green" | "red" | "neutral";
  emoji?: string;
  sublabel?: string;
  className?: string;
}

export const MetricCard = memo(function MetricCard({
  label,
  value,
  delta,
  deltaColor = "neutral",
  emoji,
  sublabel,
  className,
}: MetricCardProps) {
  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-card p-4",
        className
      )}
    >
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <div className="mt-1 flex items-baseline gap-2">
        {emoji && <span className="text-lg">{emoji}</span>}
        <span className="text-2xl font-bold tabular-nums">{value}</span>
      </div>
      {delta && (
        <p
          className={cn("mt-0.5 text-xs font-medium", {
            "text-green-400": deltaColor === "green",
            "text-red-400": deltaColor === "red",
            "text-muted-foreground": deltaColor === "neutral",
          })}
        >
          {delta}
        </p>
      )}
      {sublabel && (
        <p className="mt-0.5 text-xs text-muted-foreground">{sublabel}</p>
      )}
    </div>
  );
});
