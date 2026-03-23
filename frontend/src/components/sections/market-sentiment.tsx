"use client";

import { useMemo } from "react";
import { useMarkets } from "@/lib/hooks/use-api";
import { MarketIndex } from "@/components/charts/market-index";
import { HelperButton } from "@/components/shared/helper-button";
import { MetricSkeleton } from "@/components/shared/loading-skeleton";

export function MarketSentiment() {
  const { data, isLoading } = useMarkets();

  const { markets, dataSummary, marketPct, sentimentLabel, sentimentColor } =
    useMemo(() => {
      // Deduplicate markets — API may return multiple entries per symbol (different dates).
      // Keep the latest by timestamp for each symbol.
      const allMarkets = data?.data ?? [];
      const latestBySymbol = new Map<string, (typeof allMarkets)[0]>();
      for (const m of allMarkets) {
        const existing = latestBySymbol.get(m.symbol);
        if (!existing || m.timestamp > existing.timestamp) {
          latestBySymbol.set(m.symbol, m);
        }
      }
      const mkts = Array.from(latestBySymbol.values());

      // Build data summary for helper button
      const summary = mkts
        .map((m) => {
          const pct = parseFloat(m.change_percent) || 0;
          return `${m.symbol}: $${(m.price ?? 0).toFixed(2)} (${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%)`;
        })
        .join("\n");

      // Market sentiment: average across all indices (0-1 scale), display as integer
      const marketScore = mkts.length > 0
        ? mkts.reduce((sum, m) => sum + (m.market_sentiment ?? 0), 0) / mkts.length
        : 0;
      const pct = Math.round(marketScore * 100);
      const label =
        pct < 40 ? "Bearish \uD83D\uDC3B" : pct >= 60 ? "Bullish \uD83D\uDC02" : "Neutral \u2696\uFE0F";
      const color =
        pct < 40 ? "text-red-400" : pct >= 60 ? "text-green-400" : "text-muted-foreground";

      return {
        markets: mkts,
        dataSummary: summary,
        marketPct: pct,
        sentimentLabel: label,
        sentimentColor: color,
      };
    }, [data]);

  if (isLoading) {
    return (
      <div>
        <h2 className="mb-1 text-lg font-semibold">Market Sentiment</h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <MetricSkeleton key={i} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-1 flex items-center gap-2">
        <h2 className="text-lg font-semibold">Market Sentiment</h2>
        {markets.length > 0 && (
          <HelperButton
            chartType="market_sentiment"
            dataSummary={dataSummary}
          />
        )}
      </div>
      <p className="mb-3 text-xs text-muted-foreground">
        Markets respond to mood before they respond to news.
      </p>
      {markets.length > 0 && (
        <div className="mb-3 flex items-baseline gap-3">
          <span className="text-2xl font-bold tabular-nums">{marketPct}</span>
          <span className={`text-sm font-medium ${sentimentColor}`}>{sentimentLabel}</span>
          <span className="text-xs text-muted-foreground">Based on {markets.length} global indices</span>
        </div>
      )}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {markets.map((m) => (
          <MarketIndex key={m.symbol} market={m} />
        ))}
      </div>
    </div>
  );
}
