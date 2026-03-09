"use client";

import { useMemo } from "react";
import { useEconomicData } from "@/lib/hooks/use-api";
import { EconomicIndicator } from "@/components/charts/economic-indicator";
import { HelperButton } from "@/components/shared/helper-button";
import { MetricSkeleton } from "@/components/shared/loading-skeleton";
import type { EconomicIndicator as EconData } from "@/lib/types";

export function EconomicIndicators() {
  const { data, isLoading } = useEconomicData(730);

  if (isLoading) {
    return (
      <div>
        <h2 className="mb-1 text-lg font-semibold">Economic Indicators</h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <MetricSkeleton key={i} />
          ))}
        </div>
      </div>
    );
  }

  const { latestByName, dataSummary } = useMemo(() => {
    const allIndicators = data?.data ?? [];

    // Group by metric_name, get latest + previous for delta
    const grouped = new Map<string, EconData[]>();
    for (const ind of allIndicators) {
      const list = grouped.get(ind.metric_name) || [];
      list.push(ind);
      grouped.set(ind.metric_name, list);
    }

    const latest: Array<{
      indicator: EconData;
      previousValue?: number;
    }> = [];

    for (const [, items] of grouped) {
      // Sort by date descending
      items.sort(
        (a, b) =>
          new Date(b.snapshot_date).getTime() -
          new Date(a.snapshot_date).getTime()
      );
      latest.push({
        indicator: items[0],
        previousValue: items.length > 1 ? items[1].metric_value : undefined,
      });
    }

    // Build data summary for helper button
    const summary = latest
      .map(
        ({ indicator }) =>
          `${indicator.metric_name}: ${indicator.metric_value}`
      )
      .join("\n");

    return { latestByName: latest, dataSummary: summary };
  }, [data]);

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <h2 className="text-lg font-semibold">Economic Indicators</h2>
        {latestByName.length > 0 && (
          <HelperButton
            chartType="economic_indicators"
            dataSummary={dataSummary}
          />
        )}
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        {latestByName.map(({ indicator, previousValue }) => (
          <EconomicIndicator
            key={indicator.metric_name}
            indicator={indicator}
            previousValue={previousValue}
          />
        ))}
      </div>
    </div>
  );
}
