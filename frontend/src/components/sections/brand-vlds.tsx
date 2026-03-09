"use client";

import { useState } from "react";
import { useDashboardStore } from "@/store/dashboard-store";
import { useBrandVLDS, useChartExplain } from "@/lib/hooks/use-api";
import { MetricCard } from "@/components/charts/metric-card";
import { HelperButton } from "@/components/shared/helper-button";
import { MetricSkeleton } from "@/components/shared/loading-skeleton";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronUp, Loader2 } from "lucide-react";

export function BrandVLDS() {
  const focusedBrand = useDashboardStore((s) => s.focusedBrand);
  const { data, isLoading } = useBrandVLDS(focusedBrand || "");
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [insightLoading, setInsightLoading] = useState(false);
  const [insight, setInsight] = useState<string | null>(null);
  const chartExplain = useChartExplain();

  if (!focusedBrand) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-card p-6 text-center">
        <p className="text-sm text-muted-foreground">
          Select a brand from the sidebar to view VLDS metrics.
        </p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div>
        <h2 className="mb-1 text-lg font-semibold">Brand VLDS: {focusedBrand}</h2>
        <div className="grid grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <MetricSkeleton key={i} />
          ))}
        </div>
      </div>
    );
  }

  const vlds = data?.vlds;
  if (!vlds) {
    return (
      <div>
        <h2 className="mb-1 text-lg font-semibold">Brand VLDS: {focusedBrand}</h2>
        <p className="text-sm text-muted-foreground">
          {data?.reason || "No VLDS data available for this brand."}
        </p>
      </div>
    );
  }

  const v = vlds.velocity ?? 0;
  const l = vlds.longevity ?? 0;
  const d = vlds.density ?? 0;
  const s = vlds.scarcity ?? 0;

  const vLabel = vlds.velocity_label || (v >= 0.7 ? "Surging" : v >= 0.4 ? "Growing" : "Quiet");
  const lLabel = vlds.longevity_label || (l >= 0.7 ? "Enduring" : l >= 0.4 ? "Building" : "Emerging");
  const dLabel = vlds.density_label || (d >= 0.7 ? "Saturated" : d >= 0.4 ? "Moderate" : "Sparse");
  const sLabel = vlds.scarcity_label || (s >= 0.7 ? "White Space" : s >= 0.4 ? "Some Gaps" : "Crowded");

  const dataSummary = `Brand: ${focusedBrand}\nVelocity: ${Math.round(v * 100)}% (${vLabel})\nLongevity: ${Math.round(l * 100)}% (${lLabel})\nDensity: ${Math.round(d * 100)}% (${dLabel})\nScarcity: ${Math.round(s * 100)}% (${sLabel})`;

  const topTopics = vlds.top_topics_detailed ?? [];
  const topEmotions = vlds.top_emotions_detailed ?? [];
  const scarceTopics = vlds.scarce_topics_detailed ?? [];
  const hasDetails = topTopics.length > 0 || topEmotions.length > 0 || scarceTopics.length > 0;

  async function handleExplainBrand() {
    setInsightLoading(true);
    try {
      const topEmotionNames = topEmotions.slice(0, 3).map((e) => e.emotion).join(", ");
      const topTopicNames = topTopics.slice(0, 3).map((t) => t.topic).join(", ");
      const whiteSpaceNames = scarceTopics.slice(0, 3).map((s) => s.topic).join(", ");
      const summary = `${focusedBrand}: Velocity=${Math.round(v * 100)}% (${vLabel}), Longevity=${Math.round(l * 100)}% (${lLabel}), Density=${Math.round(d * 100)}% (${dLabel}), Scarcity=${Math.round(s * 100)}% (${sLabel}), Empathy=${vlds?.empathy_label || "N/A"}\nTop Emotions: ${topEmotionNames}\nTop Narratives: ${topTopicNames}\nWhite Space: ${whiteSpaceNames || "None"}`;
      const result = await chartExplain.mutateAsync({
        chart_type: "brand_vlds",
        data_summary: summary,
      });
      setInsight(result.explanation);
    } catch {
      setInsight("Could not generate insight.");
    } finally {
      setInsightLoading(false);
    }
  }

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <h2 className="text-lg font-semibold">Brand VLDS: {focusedBrand}</h2>
        <HelperButton chartType="brand_vlds" dataSummary={dataSummary} />
      </div>
      <p className="mb-3 text-xs text-muted-foreground">
        Velocity, Longevity, Density, Scarcity metrics for this specific brand.
      </p>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <MetricCard label="Velocity" value={`${Math.round(v * 100)}%`} sublabel={vLabel} />
        <MetricCard label="Longevity" value={`${Math.round(l * 100)}%`} sublabel={lLabel} />
        <MetricCard label="Density" value={`${Math.round(d * 100)}%`} sublabel={dLabel} />
        <MetricCard label="Scarcity" value={`${Math.round(s * 100)}%`} sublabel={sLabel} />
      </div>

      {/* Expandable Details */}
      {hasDetails && (
        <div className="mt-3">
          <Button
            variant="ghost"
            size="sm"
            className="text-xs"
            onClick={() => setDetailsOpen(!detailsOpen)}
          >
            {detailsOpen ? <ChevronUp className="mr-1 h-3 w-3" /> : <ChevronDown className="mr-1 h-3 w-3" />}
            Brand Intelligence Details
          </Button>

          {detailsOpen && (
            <div className="mt-2 rounded-lg border border-border bg-card p-4 space-y-4">
              <p className="text-xs text-muted-foreground">
                Based on {vlds.total_posts ?? 0} posts mentioning &ldquo;{focusedBrand}&rdquo;
              </p>

              {/* Key Insights */}
              {(vlds.velocity_insight || vlds.longevity_insight || vlds.density_insight || vlds.emotion_insight) && (
                <div>
                  <p className="mb-1 text-sm font-medium">Key Insights</p>
                  <div className="space-y-1 text-xs text-muted-foreground">
                    {vlds.velocity_insight && <p><span className="font-medium text-foreground">Velocity:</span> {vlds.velocity_insight}</p>}
                    {vlds.longevity_insight && <p><span className="font-medium text-foreground">Longevity:</span> {vlds.longevity_insight}</p>}
                    {vlds.density_insight && <p><span className="font-medium text-foreground">Density:</span> {vlds.density_insight}</p>}
                    {vlds.emotion_insight && <p><span className="font-medium text-foreground">Emotion:</span> {vlds.emotion_insight}</p>}
                  </div>
                </div>
              )}

              <div className="grid gap-4 md:grid-cols-2">
                {/* Top Narratives */}
                {topTopics.length > 0 && (
                  <div>
                    <p className="mb-1 text-sm font-medium">Top Narratives</p>
                    <p className="mb-2 text-[10px] text-muted-foreground">What topics dominate coverage</p>
                    <div className="space-y-1">
                      {topTopics.map((t) => (
                        <p key={t.topic} className="text-xs">
                          <span className="font-medium">{t.topic}</span>
                          <span className="text-muted-foreground"> &mdash; {t.percentage}% ({t.count} posts)</span>
                        </p>
                      ))}
                    </div>
                  </div>
                )}

                {/* Dominant Emotions */}
                {topEmotions.length > 0 && (
                  <div>
                    <p className="mb-1 text-sm font-medium">Dominant Emotions</p>
                    <p className="mb-2 text-[10px] text-muted-foreground">How people feel when discussing this brand</p>
                    <div className="space-y-1">
                      {topEmotions.map((e) => (
                        <p key={e.emotion} className="text-xs">
                          <span className="font-medium capitalize">{e.emotion}</span>
                          <span className="text-muted-foreground"> &mdash; {e.percentage}% ({e.count} posts)</span>
                        </p>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* White Space Opportunities */}
              <div>
                <p className="mb-1 text-sm font-medium">White Space Opportunities</p>
                <p className="mb-2 text-[10px] text-muted-foreground">
                  Topics with &lt;10% share &mdash; potential areas to own the narrative
                </p>
                {scarceTopics.length > 0 ? (
                  <div className="grid grid-cols-3 gap-2">
                    {scarceTopics.slice(0, 3).map((t) => (
                      <MetricCard
                        key={t.topic}
                        label={t.topic ?? ""}
                        value={`${t.percentage}%`}
                        sublabel={`${t.count} posts`}
                      />
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    No clear white space opportunities &mdash; coverage is evenly distributed or saturated.
                  </p>
                )}
                {scarceTopics.length > 3 && (
                  <p className="mt-1 text-[10px] text-muted-foreground">
                    Also underrepresented: {scarceTopics.slice(3).map((s) => s.topic).join(", ")}
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Explain Brand button */}
      <div className="mt-3">
        <Button
          variant="outline"
          size="sm"
          className="text-xs"
          onClick={handleExplainBrand}
          disabled={insightLoading}
        >
          {insightLoading ? (
            <><Loader2 className="mr-1 h-3 w-3 animate-spin" /> Analyzing...</>
          ) : (
            "\uD83D\uDD0D Explain This Brand"
          )}
        </Button>
        {insight && (
          <div className="mt-2 rounded-lg border border-border bg-muted p-3">
            <p className="mb-1 text-sm font-medium">Brand Strategic Insight</p>
            <p className="whitespace-pre-wrap text-xs">{insight}</p>
          </div>
        )}
      </div>
    </div>
  );
}
