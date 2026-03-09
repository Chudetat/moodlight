"use client";

import { useMemo } from "react";
import { useCommodities } from "@/lib/hooks/use-api";
import { CommodityPrice } from "@/components/charts/commodity-price";
import { HelperButton } from "@/components/shared/helper-button";
import { MetricSkeleton } from "@/components/shared/loading-skeleton";
import type { CommodityPrice as CommodityData } from "@/lib/types";

export function CommodityPrices() {
  const { data, isLoading } = useCommodities(90);

  if (isLoading) {
    return (
      <div>
        <h2 className="mb-1 text-lg font-semibold">Commodity Prices</h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <MetricSkeleton key={i} />
          ))}
        </div>
      </div>
    );
  }

  const { latestByName, dataSummary } = useMemo(() => {
    const allCommodities = data?.data ?? [];

    // Filter to price metrics only, group by scope_name (commodity name)
    const priceEntries = allCommodities.filter((c) => c.metric_name === "price");
    const grouped = new Map<string, CommodityData[]>();
    for (const c of priceEntries) {
      const list = grouped.get(c.scope_name) || [];
      list.push(c);
      grouped.set(c.scope_name, list);
    }

    const latest: Array<{
      commodity: CommodityData;
      previousPrice?: number;
    }> = [];

    for (const [, items] of grouped) {
      items.sort(
        (a, b) =>
          new Date(b.snapshot_date).getTime() -
          new Date(a.snapshot_date).getTime()
      );
      latest.push({
        commodity: items[0],
        previousPrice: items.length > 1 ? items[1].metric_value : undefined,
      });
    }

    // Build data summary for helper button
    const summary = latest
      .map(
        ({ commodity, previousPrice }) =>
          `${commodity.scope_name}: $${(commodity.metric_value ?? 0).toFixed(2)}${
            previousPrice
              ? ` (prev: $${previousPrice.toFixed(2)})`
              : ""
          }`
      )
      .join("\n");

    return { latestByName: latest, dataSummary: summary };
  }, [data]);

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <h2 className="text-lg font-semibold">Commodity Prices</h2>
        {latestByName.length > 0 && (
          <HelperButton
            chartType="commodity_prices"
            dataSummary={dataSummary}
          />
        )}
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {latestByName.map(({ commodity, previousPrice }) => (
          <CommodityPrice
            key={commodity.scope_name}
            commodity={commodity}
            previousPrice={previousPrice}
          />
        ))}
      </div>
    </div>
  );
}
