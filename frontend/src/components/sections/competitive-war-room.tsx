"use client";

import { useAuth } from "@/lib/hooks/use-auth";
import { useBrands, useCompetitive } from "@/lib/hooks/use-api";
import { FeatureGate } from "@/components/layout/feature-gate";
import { BarChart } from "@/components/charts/bar-chart";
import { HelperButton } from "@/components/shared/helper-button";
import { ChartSkeleton } from "@/components/shared/loading-skeleton";

function WarRoomContent() {
  const { username } = useAuth();
  const { data: brandsData } = useBrands(username);
  const firstBrand = brandsData?.brands?.[0] ?? "";
  const { data: compData, isLoading } = useCompetitive(firstBrand);

  if (isLoading || !firstBrand) {
    return <ChartSkeleton />;
  }

  const snapshot = compData?.snapshot;
  if (!snapshot) {
    return (
      <p className="py-4 text-center text-sm text-muted-foreground">
        No competitive data available. Add brands to your watchlist.
      </p>
    );
  }

  // Build SOV chart data from metrics
  const sovData: Array<{ brand: string; sov: number }> = [];
  const metrics = snapshot.metrics as Record<string, unknown>;

  if (metrics && typeof metrics === "object") {
    // Try to extract SOV data from various possible structures
    for (const competitor of snapshot.competitors) {
      const compMetrics = metrics[competitor.name] as Record<string, number> | undefined;
      if (compMetrics?.share_of_voice !== undefined) {
        sovData.push({
          brand: competitor.name,
          sov: compMetrics.share_of_voice,
        });
      }
    }
  }

  const dataSummary = `Brand: ${firstBrand}\nCompetitors: ${snapshot.competitors.map((c) => c.name).join(", ")}\nSOV: ${sovData.map((d) => `${d.brand}: ${d.sov}%`).join(", ")}`;

  return (
    <div className="space-y-4">
      {/* Competitors list */}
      <div className="flex flex-wrap gap-2">
        {snapshot.competitors.map((c) => (
          <span
            key={c.name}
            className="rounded-full bg-muted px-3 py-1 text-xs"
          >
            {c.name}
          </span>
        ))}
      </div>

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
          />
        </div>
      )}
    </div>
  );
}

export function CompetitiveWarRoom() {
  return (
    <div>
      <h2 className="mb-3 text-lg font-semibold">Competitive War Room</h2>
      <FeatureGate feature="competitive_war_room">
        <WarRoomContent />
      </FeatureGate>
    </div>
  );
}
