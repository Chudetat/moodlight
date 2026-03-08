"use client";

import { useCommodities } from "@/lib/hooks/use-api";
import { CommodityPrice } from "@/components/charts/commodity-price";
import { HelperButton } from "@/components/shared/helper-button";
import { MetricSkeleton } from "@/components/shared/loading-skeleton";
import type { CommodityPrice as CommodityData } from "@/lib/types";

export function CommodityPrices() {
  const { data, isLoading } = useCommodities(7);

  if (isLoading) {
    return (
      <div>
        <h2 className="mb-3 text-lg font-semibold">Commodity Prices</h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <MetricSkeleton key={i} />
          ))}
        </div>
      </div>
    );
  }

  const allCommodities = data?.data ?? [];

  // Group by commodity_name, get latest + previous for delta
  const grouped = new Map<string, CommodityData[]>();
  for (const c of allCommodities) {
    const list = grouped.get(c.commodity_name) || [];
    list.push(c);
    grouped.set(c.commodity_name, list);
  }

  const latestByName: Array<{
    commodity: CommodityData;
    previousPrice?: number;
  }> = [];

  for (const [, items] of grouped) {
    items.sort(
      (a, b) =>
        new Date(b.snapshot_date).getTime() -
        new Date(a.snapshot_date).getTime()
    );
    latestByName.push({
      commodity: items[0],
      previousPrice: items.length > 1 ? items[1].price : undefined,
    });
  }

  // Build data summary for helper button
  const dataSummary = latestByName
    .map(
      ({ commodity, previousPrice }) =>
        `${commodity.commodity_name}: $${commodity.price.toFixed(2)} ${commodity.currency}${
          previousPrice
            ? ` (prev: $${previousPrice.toFixed(2)})`
            : ""
        }`
    )
    .join("\n");

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
            key={commodity.commodity_name}
            commodity={commodity}
            previousPrice={previousPrice}
          />
        ))}
      </div>
    </div>
  );
}
