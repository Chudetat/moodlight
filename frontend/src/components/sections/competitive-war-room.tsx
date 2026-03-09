"use client";

import { useState } from "react";
import { useAuth } from "@/lib/hooks/use-auth";
import { useBrands, useCompetitive, useChartExplain } from "@/lib/hooks/use-api";
import { FeatureGate } from "@/components/layout/feature-gate";
import { BarChart } from "@/components/charts/bar-chart";
import { MetricCard } from "@/components/charts/metric-card";
import { HelperButton } from "@/components/shared/helper-button";
import { ChartSkeleton } from "@/components/shared/loading-skeleton";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";

interface BrandWarRoomProps {
  brand: string;
}

function BrandWarRoom({ brand }: BrandWarRoomProps) {
  const { data: compData, isLoading } = useCompetitive(brand);
  const chartExplain = useChartExplain();
  const [insightLoading, setInsightLoading] = useState(false);
  const [insight, setInsight] = useState<string | null>(null);

  if (isLoading) return <ChartSkeleton />;

  const snapshot = compData?.snapshot;
  if (!snapshot) {
    return (
      <p className="py-4 text-center text-sm text-muted-foreground">
        Competitive snapshot not yet available — will appear after next pipeline run.
      </p>
    );
  }

  // The snapshot is a flat JSON object:
  //   { "BrandName": { vlds: {...}, mention_count: N }, "Competitor": { ... },
  //     share_of_voice: { ... }, competitive_gaps: { ... } }
  const snapshotObj = snapshot as Record<string, unknown>;
  const sovObj = (snapshotObj.share_of_voice ?? {}) as Record<string, number>;
  const gaps = (snapshotObj.competitive_gaps ?? {}) as Record<string, number>;

  // Build SOV chart data
  const sovData = Object.entries(sovObj)
    .filter(([, v]) => typeof v === "number")
    .map(([name, sov]) => ({ brand: name, sov: Math.round(sov * 10) / 10 }))
    .sort((a, b) => b.sov - a.sov);

  // Extract competitor names (keys that are not share_of_voice or competitive_gaps)
  const competitorNames = Object.keys(snapshotObj).filter(
    (k) => k !== "share_of_voice" && k !== "competitive_gaps" && k !== brand
  );

  // Build VLDS gap metrics
  const vGap = gaps.velocity_gap ?? 0;
  const lGap = gaps.longevity_gap ?? 0;
  const dGap = gaps.density_gap ?? 0;
  const sGap = gaps.scarcity_gap ?? 0;

  const dataSummary = `Brand: ${brand}\nCompetitors: ${competitorNames.join(", ")}\nSOV: ${sovData.map((d) => `${d.brand}: ${d.sov}%`).join(", ")}\nVelocity gap: ${vGap.toFixed(2)}, Longevity gap: ${lGap.toFixed(2)}, Density gap: ${dGap.toFixed(2)}, Scarcity gap: ${sGap.toFixed(2)}`;

  return (
    <div className="space-y-4">
      {/* Competitors */}
      {competitorNames.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {competitorNames.map((name) => {
            const info = snapshotObj[name] as
              | { mention_count?: number }
              | undefined;
            return (
              <span
                key={name}
                className="rounded-full bg-muted px-3 py-1 text-xs"
              >
                {name}
                {info?.mention_count != null && (
                  <span className="ml-1 text-muted-foreground">
                    ({info.mention_count} mentions)
                  </span>
                )}
              </span>
            );
          })}
        </div>
      )}

      {/* SOV chart */}
      {sovData.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="mb-2 flex items-center gap-2">
            <p className="text-sm font-medium">Share of Voice</p>
            <HelperButton
              chartType="competitive_war_room"
              dataSummary={dataSummary}
            />
          </div>
          <BarChart
            data={sovData}
            keys={["sov"]}
            indexBy="brand"
            layout="horizontal"
            height={Math.max(200, sovData.length * 40)}
            colors={(datum) => {
              return String(datum.indexValue) === brand
                ? "#4CAF50"
                : "#78909C";
            }}
          />
        </div>
      )}

      {/* VLDS Gaps */}
      {Object.keys(gaps).length > 0 && (
        <div>
          <p className="mb-2 text-sm font-medium">VLDS Gap (vs competitors)</p>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <MetricCard
              label="Velocity"
              value={(gaps.velocity_brand ?? 0).toFixed(2)}
              sublabel={`${vGap >= 0 ? "+" : ""}${vGap.toFixed(2)} gap`}
            />
            <MetricCard
              label="Longevity"
              value={(gaps.longevity_brand ?? 0).toFixed(2)}
              sublabel={`${lGap >= 0 ? "+" : ""}${lGap.toFixed(2)} gap`}
            />
            <MetricCard
              label="Density"
              value={(gaps.density_brand ?? 0).toFixed(2)}
              sublabel={`${dGap >= 0 ? "+" : ""}${dGap.toFixed(2)} gap`}
            />
            <MetricCard
              label="Scarcity"
              value={(gaps.scarcity_brand ?? 0).toFixed(2)}
              sublabel={`${sGap >= 0 ? "+" : ""}${sGap.toFixed(2)} gap`}
            />
          </div>
        </div>
      )}

      {/* AI Competitive Insight */}
      <div className="mt-3">
        <Button
          variant="outline"
          size="sm"
          className="text-xs"
          onClick={async () => {
            setInsightLoading(true);
            try {
              const compNames = competitorNames.join(", ");
              const sovSummary = sovData.map((d) => `${d.brand}: ${d.sov}%`).join(", ");
              const summary = `Brand: ${brand}\nCompetitors: ${compNames}\nSOV: ${sovSummary}\nVelocity gap: ${vGap.toFixed(2)}, Longevity gap: ${lGap.toFixed(2)}, Density gap: ${dGap.toFixed(2)}, Scarcity gap: ${sGap.toFixed(2)}`;
              const result = await chartExplain.mutateAsync({
                chart_type: "competitive_war_room",
                data_summary: summary,
              });
              setInsight(result.explanation);
            } catch {
              setInsight("Could not generate competitive insight.");
            } finally {
              setInsightLoading(false);
            }
          }}
          disabled={insightLoading}
        >
          {insightLoading ? (
            <><Loader2 className="mr-1 h-3 w-3 animate-spin" /> Analyzing...</>
          ) : (
            "\uD83D\uDD0D Generate AI Competitive Insight"
          )}
        </Button>
        {insight && (
          <div className="mt-2 rounded-lg border border-border bg-muted p-3">
            <p className="mb-1 text-sm font-medium">Competitive Insight</p>
            <p className="whitespace-pre-wrap text-xs">{insight}</p>
          </div>
        )}
      </div>
    </div>
  );
}

function WarRoomContent() {
  const { username } = useAuth();
  const { data: brandsData } = useBrands(username);
  const brands = brandsData?.brands ?? [];

  if (brands.length === 0) {
    return (
      <p className="py-4 text-center text-sm text-muted-foreground">
        Add brands to your watchlist to see competitive intelligence.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      {brands.map((brand) => (
        <div key={brand}>
          <h3 className="mb-2 text-sm font-semibold">{brand}</h3>
          <BrandWarRoom brand={brand} />
        </div>
      ))}
    </div>
  );
}

export function CompetitiveWarRoom() {
  return (
    <div>
      <h2 className="mb-1 text-lg font-semibold">Competitive War Room</h2>
      <FeatureGate feature="competitive_war_room">
        <WarRoomContent />
      </FeatureGate>
    </div>
  );
}
