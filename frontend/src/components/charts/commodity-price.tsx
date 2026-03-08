"use client";

import { COMMODITY_NAMES } from "@/lib/constants";
import type { CommodityPrice as CommodityData } from "@/lib/types";

interface CommodityPriceProps {
  commodity: CommodityData;
  previousPrice?: number;
}

export function CommodityPrice({
  commodity,
  previousPrice,
}: CommodityPriceProps) {
  const name =
    COMMODITY_NAMES[commodity.scope_name] || commodity.scope_name;

  // Compute delta from previous price entry (as the dashboard does)
  let deltaPct: number | undefined;
  if (previousPrice && previousPrice > 0) {
    deltaPct =
      ((commodity.metric_value - previousPrice) / previousPrice) * 100;
  }

  const isPositive = (deltaPct ?? 0) >= 0;

  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3">
      <p className="text-xs font-medium text-muted-foreground">{name}</p>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="text-xl font-bold tabular-nums">
          ${commodity.metric_value.toFixed(2)}
        </span>
        {deltaPct !== undefined && Math.abs(deltaPct) > 0.001 && (
          <span
            className={`text-xs font-medium tabular-nums ${
              isPositive ? "text-green-400" : "text-red-400"
            }`}
          >
            {isPositive ? "\u2191" : "\u2193"}{" "}
            {isPositive ? "+" : ""}
            {deltaPct.toFixed(2)}%
          </span>
        )}
      </div>
      <p className="mt-0.5 text-[10px] text-muted-foreground">
        USD &middot;{" "}
        {new Date(commodity.snapshot_date).toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
        })}
      </p>
    </div>
  );
}
