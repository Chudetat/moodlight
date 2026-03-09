"use client";

import { useState } from "react";
import { useDashboardStore } from "@/store/dashboard-store";
import { useBrandVLDS, useChartExplain } from "@/lib/hooks/use-api";
import { MetricCard } from "@/components/charts/metric-card";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";

function BrandColumn({ brand }: { brand: string }) {
  const { data } = useBrandVLDS(brand);
  const vlds = data?.vlds;

  if (!vlds) {
    return (
      <div className="text-center">
        <p className="mb-2 text-sm font-semibold">{brand}</p>
        <p className="text-xs text-muted-foreground">Gathering data...</p>
      </div>
    );
  }

  const v = vlds.velocity ?? 0;
  const l = vlds.longevity ?? 0;
  const d = vlds.density ?? 0;
  const s = vlds.scarcity ?? 0;

  return (
    <div>
      <p className="mb-2 text-sm font-semibold">{brand}</p>

      {/* VLDS metrics */}
      <div className="space-y-1">
        <MetricCard
          label="Posts"
          value={vlds.total_posts ?? 0}
        />
        <MetricCard
          label="Velocity"
          value={`${Math.round(v * 100)}%`}
          sublabel={vlds.velocity_label || ""}
        />
        <MetricCard
          label="Longevity"
          value={`${Math.round(l * 100)}%`}
          sublabel={vlds.longevity_label || ""}
        />
        <MetricCard
          label="Density"
          value={`${Math.round(d * 100)}%`}
          sublabel={vlds.density_label || ""}
        />
        <MetricCard
          label="Scarcity"
          value={`${Math.round(s * 100)}%`}
          sublabel={vlds.scarcity_label || ""}
        />
      </div>

      {/* Empathy */}
      <div className="mt-3">
        <p className="mb-1 text-xs font-medium">Empathy</p>
        <p className="text-xs text-muted-foreground">
          {vlds.empathy_label || "N/A"}
        </p>
      </div>

      {/* Top Emotions */}
      {(vlds.top_emotions_detailed ?? []).length > 0 && (
        <div className="mt-3">
          <p className="mb-1 text-xs font-medium">Dominant Emotions</p>
          {(vlds.top_emotions_detailed ?? []).slice(0, 3).map((e) => (
            <p key={e.emotion} className="text-xs text-muted-foreground">
              {(e.emotion ?? "").charAt(0).toUpperCase() + (e.emotion ?? "").slice(1)}: {e.percentage}%
            </p>
          ))}
        </div>
      )}

      {/* Top Narratives */}
      {(vlds.top_topics_detailed ?? []).length > 0 && (
        <div className="mt-3">
          <p className="mb-1 text-xs font-medium">Top Narratives</p>
          {(vlds.top_topics_detailed ?? []).slice(0, 3).map((t) => (
            <p key={t.topic} className="text-xs text-muted-foreground">
              {t.topic}: {t.percentage}%
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

export function BrandComparison() {
  const { compareMode, compareBrands } = useDashboardStore();
  const chartExplain = useChartExplain();
  const [insightLoading, setInsightLoading] = useState(false);
  const [insight, setInsight] = useState<string | null>(null);

  // Fetch VLDS for each brand to build summary for explain button
  const brand1 = compareBrands[0]?.trim() || "";
  const brand2 = compareBrands[1]?.trim() || "";
  const brand3 = compareBrands[2]?.trim() || "";
  const { data: data1 } = useBrandVLDS(brand1);
  const { data: data2 } = useBrandVLDS(brand2);
  const { data: data3 } = useBrandVLDS(brand3);

  if (!compareMode) return null;

  const activeBrands = compareBrands.filter((b) => b.trim());
  if (activeBrands.length < 2) {
    return (
      <div>
        <h2 className="mb-1 text-lg font-semibold">Brand Comparison</h2>
        <p className="text-sm text-muted-foreground">
          Select at least 2 brands in the sidebar to compare.
        </p>
      </div>
    );
  }

  async function handleExplain() {
    setInsightLoading(true);
    try {
      const allData = [
        { brand: brand1, data: data1 },
        { brand: brand2, data: data2 },
        { brand: brand3, data: data3 },
      ].filter((d) => d.brand && d.data?.vlds);

      const summary = allData
        .map((d) => {
          const v = d.data!.vlds!;
          return `${d.brand}: Velocity=${Math.round((v.velocity ?? 0) * 100)}%, Longevity=${Math.round((v.longevity ?? 0) * 100)}%, Density=${Math.round((v.density ?? 0) * 100)}%, Scarcity=${Math.round((v.scarcity ?? 0) * 100)}%, Empathy=${v.empathy_label || "N/A"}`;
        })
        .join("\n");

      const result = await chartExplain.mutateAsync({
        chart_type: "brand_comparison",
        data_summary: `Brands compared: ${activeBrands.join(", ")}\n\nVLDS Metrics:\n${summary}`,
      });
      setInsight(result.explanation);
    } catch {
      setInsight("Could not generate comparison insight.");
    } finally {
      setInsightLoading(false);
    }
  }

  return (
    <div>
      <h2 className="mb-1 text-lg font-semibold">Brand Comparison</h2>
      <p className="mb-3 text-xs text-muted-foreground">
        Comparing VLDS metrics: {activeBrands.join(" vs ")}
      </p>

      <div
        className="grid gap-4"
        style={{ gridTemplateColumns: `repeat(${activeBrands.length}, 1fr)` }}
      >
        {activeBrands.map((brand) => (
          <BrandColumn key={brand} brand={brand} />
        ))}
      </div>

      {/* Explain Comparison */}
      <div className="mt-4">
        <Button
          variant="outline"
          size="sm"
          className="text-xs"
          onClick={handleExplain}
          disabled={insightLoading}
        >
          {insightLoading ? (
            <><Loader2 className="mr-1 h-3 w-3 animate-spin" /> Analyzing...</>
          ) : (
            "\uD83D\uDD0D Explain This Comparison"
          )}
        </Button>
        {insight && (
          <div className="mt-2 rounded-lg border border-border bg-muted p-3">
            <p className="mb-1 text-sm font-medium">Comparison Insight</p>
            <p className="whitespace-pre-wrap text-xs">{insight}</p>
          </div>
        )}
      </div>
    </div>
  );
}
