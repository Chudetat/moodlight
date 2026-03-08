"use client";

import { ECONOMIC_INDICATORS } from "@/lib/constants";
import { formatNumber } from "@/lib/utils";
import type { EconomicIndicator as EconData } from "@/lib/types";

interface EconomicIndicatorProps {
  indicator: EconData;
  previousValue?: number;
}

export function EconomicIndicator({
  indicator,
  previousValue,
}: EconomicIndicatorProps) {
  const config = ECONOMIC_INDICATORS[indicator.indicator_name];
  const label = config?.label || indicator.indicator_name;

  // Format the display value
  let displayValue: string;
  if (config?.format === "number") {
    displayValue = formatNumber(indicator.value);
  } else if (config?.format === "percent" || config?.format === "currency") {
    displayValue = `${indicator.value.toFixed(2)}%`;
  } else {
    displayValue = String(indicator.value);
  }

  // Compute delta
  let deltaStr: string | undefined;
  let deltaDir: "up" | "down" | "none" = "none";

  if (
    previousValue !== undefined &&
    indicator.indicator_name !== "Nonfarm Payroll"
  ) {
    const diff = indicator.value - previousValue;
    if (Math.abs(diff) > 0.001) {
      deltaDir = diff > 0 ? "up" : "down";
      // For Fed Funds Rate, hide delta when exactly 0
      if (
        indicator.indicator_name === "Federal Funds Rate" &&
        Math.abs(diff) < 0.001
      ) {
        deltaStr = undefined;
      } else {
        const sign = diff > 0 ? "+" : "";
        deltaStr = `${sign}${diff.toFixed(2)}${config?.unit || ""}`;
      }
    }
  }

  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="text-xl font-bold tabular-nums">{displayValue}</span>
        {deltaStr && (
          <span
            className={`text-xs font-medium ${
              deltaDir === "up" ? "text-green-400" : "text-red-400"
            }`}
          >
            {deltaDir === "up" ? "\u2191" : "\u2193"} {deltaStr}
          </span>
        )}
      </div>
      <p className="mt-0.5 text-[10px] text-muted-foreground">
        {new Date(indicator.snapshot_date).toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
          year: "numeric",
        })}
      </p>
    </div>
  );
}
