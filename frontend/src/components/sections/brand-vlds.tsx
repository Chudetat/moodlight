"use client";

import { useDashboardStore } from "@/store/dashboard-store";
import { useBrandVLDS } from "@/lib/hooks/use-api";
import { MetricCard } from "@/components/charts/metric-card";
import { HelperButton } from "@/components/shared/helper-button";
import { MetricSkeleton } from "@/components/shared/loading-skeleton";

export function BrandVLDS() {
  const focusedBrand = useDashboardStore((s) => s.focusedBrand);
  const { data, isLoading } = useBrandVLDS(focusedBrand || "");

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
        <h2 className="mb-3 text-lg font-semibold">Brand VLDS: {focusedBrand}</h2>
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
        <h2 className="mb-3 text-lg font-semibold">Brand VLDS: {focusedBrand}</h2>
        <p className="text-sm text-muted-foreground">
          {data?.reason || "No VLDS data available for this brand."}
        </p>
      </div>
    );
  }

  const dataSummary = `Brand: ${focusedBrand}\nVelocity: ${vlds.velocity.toFixed(2)}\nLongevity: ${vlds.longevity.toFixed(2)}\nDensity: ${vlds.density.toFixed(2)}\nScarcity: ${vlds.scarcity.toFixed(2)}`;

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <h2 className="text-lg font-semibold">Brand VLDS: {focusedBrand}</h2>
        <HelperButton chartType="brand_vlds" dataSummary={dataSummary} />
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <MetricCard label="Velocity" value={vlds.velocity.toFixed(2)} />
        <MetricCard label="Longevity" value={vlds.longevity.toFixed(2)} />
        <MetricCard label="Density" value={vlds.density.toFixed(2)} />
        <MetricCard label="Scarcity" value={vlds.scarcity.toFixed(2)} />
      </div>
    </div>
  );
}
