"use client";

import { MARKET_SYMBOLS } from "@/lib/constants";
import { formatPctChange } from "@/lib/utils";
import type { MarketData } from "@/lib/types";

interface MarketIndexProps {
  market: MarketData;
}

export function MarketIndex({ market }: MarketIndexProps) {
  const name = MARKET_SYMBOLS[market.symbol] || market.name || market.symbol;
  const changePct = parseFloat(market.change_percent) || 0;
  const isPositive = changePct > 0;
  const isZero = changePct === 0;

  return (
    <div className="flex items-center justify-between rounded-lg border border-border bg-card px-4 py-3">
      <div className="flex items-center gap-2">
        <span className="text-base">
          {isZero ? "\u26AA" : isPositive ? "\uD83D\uDFE2" : "\uD83D\uDD34"}
        </span>
        <span className="text-sm font-medium">{name}</span>
      </div>
      <div className="text-right">
        <p className="text-sm font-bold tabular-nums">
          ${(market.price ?? 0).toFixed(2)}
        </p>
        <p
          className={`text-xs font-medium tabular-nums ${
            isZero ? "text-muted-foreground" : isPositive ? "text-green-400" : "text-red-400"
          }`}
        >
          {formatPctChange(changePct)}
        </p>
      </div>
    </div>
  );
}
