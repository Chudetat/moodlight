"use client";

import { usePredictionMarkets } from "@/lib/hooks/use-api";
import { FeatureGate } from "@/components/layout/feature-gate";
import { HelperButton } from "@/components/shared/helper-button";
import { ChartSkeleton } from "@/components/shared/loading-skeleton";

function PredictionMarketsContent() {
  const { data, isLoading } = usePredictionMarkets();

  if (isLoading) return <ChartSkeleton />;

  // Show up to 8 highest volume markets (matching Streamlit)
  const markets = (data?.markets ?? []).slice(0, 8);
  const divergence = data?.divergence;

  if (markets.length === 0) {
    return (
      <p className="py-4 text-center text-sm text-muted-foreground">
        Prediction market data unavailable. API may be temporarily down.
      </p>
    );
  }

  const dataSummary = `Avg Market Confidence: ${(data?.avg_market_confidence ?? 0).toFixed(0)}%, Avg Social Mood: ${(data?.avg_social_mood ?? 0).toFixed(0)}, Divergence: ${(divergence?.divergence ?? 0).toFixed(0)} pts (${divergence?.status ?? "N/A"})\n\nTop Markets: ${markets.slice(0, 5).map((m) => `${m.question}: ${(m.yes_odds ?? 0).toFixed(0)}% Yes`).join("; ")}`;

  return (
    <>
      <p className="mb-3 text-xs text-muted-foreground">
        What the money says&mdash;prediction market odds vs. social sentiment
        divergence.
      </p>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {/* Left 2/3: Top markets */}
        <div className="col-span-2 space-y-0">
          <div className="mb-2 text-sm font-semibold">
            Top Markets by Volume
          </div>
          {markets.map((m, i) => {
            const icon =
              (m.yes_odds ?? 0) > 60
                ? "\uD83D\uDFE2"
                : (m.yes_odds ?? 0) < 40
                ? "\uD83D\uDD34"
                : "\uD83D\uDFE1";
            return (
              <div
                key={i}
                className={`py-2 ${
                  i < markets.length - 1 ? "border-b border-border/50" : ""
                }`}
              >
                <div className="text-sm font-medium">
                  {icon}{" "}
                  {(m.question ?? "").length > 80
                    ? (m.question ?? "").slice(0, 80) + "..."
                    : m.question ?? ""}
                </div>
                <div className="mt-1 flex gap-4 text-xs text-muted-foreground">
                  <span>
                    Yes:{" "}
                    <span className="font-medium text-foreground">
                      {(m.yes_odds ?? 0).toFixed(0)}%
                    </span>
                  </span>
                  <span>
                    No:{" "}
                    <span className="font-medium text-foreground">
                      {(m.no_odds ?? 0).toFixed(0)}%
                    </span>
                  </span>
                  <span>
                    Volume:{" "}
                    <span className="font-medium text-foreground">
                      ${(m.volume ?? 0).toLocaleString(undefined, {
                        maximumFractionDigits: 0,
                      })}
                    </span>
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Right 1/3: Divergence */}
        <div className="space-y-3">
          <div className="text-sm font-semibold">Market vs. Mood</div>
          <p className="text-xs text-muted-foreground">
            When prediction markets diverge from social sentiment, opportunities
            emerge.
          </p>
          {divergence && (
            <>
              <div>
                <div className="text-xs text-muted-foreground">
                  Avg Market Confidence
                </div>
                <div className="text-lg font-bold">
                  {(data?.avg_market_confidence ?? 0).toFixed(0)}%
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">
                  Avg Social Mood
                </div>
                <div className="text-lg font-bold">
                  {(data?.avg_social_mood ?? 0).toFixed(0)}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Divergence</div>
                <div className="text-lg font-bold">
                  {(divergence.divergence ?? 0).toFixed(0)} pts
                </div>
                <div
                  className={`text-xs font-medium ${
                    divergence.status === "High Divergence"
                      ? "text-red-400"
                      : divergence.status === "Moderate Divergence"
                      ? "text-yellow-400"
                      : "text-green-400"
                  }`}
                >
                  {divergence.status}
                </div>
              </div>
              <p className="text-xs text-muted-foreground">
                {divergence.interpretation}
              </p>
              <HelperButton
                chartType="polymarket_divergence"
                dataSummary={dataSummary}
              />
            </>
          )}
        </div>
      </div>
    </>
  );
}

export function PredictionMarkets() {
  return (
    <div>
      <h2 className="mb-1 text-lg font-semibold">Prediction Markets</h2>
      <FeatureGate feature="prediction_markets">
        <PredictionMarketsContent />
      </FeatureGate>
    </div>
  );
}
