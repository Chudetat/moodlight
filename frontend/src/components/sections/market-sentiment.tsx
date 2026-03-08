"use client";

import { useMarkets } from "@/lib/hooks/use-api";
import { MarketIndex } from "@/components/charts/market-index";
import { HelperButton } from "@/components/shared/helper-button";
import { MetricSkeleton } from "@/components/shared/loading-skeleton";

export function MarketSentiment() {
  const { data, isLoading } = useMarkets();

  if (isLoading) {
    return (
      <div>
        <h2 className="mb-3 text-lg font-semibold">Market Sentiment</h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <MetricSkeleton key={i} />
          ))}
        </div>
      </div>
    );
  }

  const markets = data?.data ?? [];

  // Build data summary for helper button
  const dataSummary = markets
    .map(
      (m) =>
        `${m.symbol}: $${m.close.toFixed(2)} (${m.change_pct >= 0 ? "+" : ""}${m.change_pct.toFixed(2)}%)`
    )
    .join("\n");

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <h2 className="text-lg font-semibold">Market Sentiment</h2>
        {markets.length > 0 && (
          <HelperButton
            chartType="market_sentiment"
            dataSummary={dataSummary}
          />
        )}
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {markets.map((m) => (
          <MarketIndex key={m.symbol} market={m} />
        ))}
      </div>
    </div>
  );
}
