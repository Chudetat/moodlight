"use client";

import { ResponsiveBar, type BarDatum } from "@nivo/bar";
import { COLORS } from "@/lib/constants";

interface BarChartProps {
  data: BarDatum[];
  keys: string[];
  indexBy: string;
  height?: number;
  layout?: "vertical" | "horizontal";
  groupMode?: "grouped" | "stacked";
  enableLabel?: boolean;
  axisBottomLegend?: string;
  axisLeftLegend?: string;
  colors?: string[] | ((datum: { id: string | number; indexValue?: string | number; data?: Record<string, unknown>; [key: string]: unknown }) => string);
}

export function BarChart({
  data,
  keys,
  indexBy,
  height = 300,
  layout = "vertical",
  groupMode = "grouped",
  enableLabel = false,
  axisBottomLegend,
  axisLeftLegend,
  colors,
}: BarChartProps) {
  return (
    <div style={{ height }}>
      <ResponsiveBar
        data={data}
        keys={keys}
        indexBy={indexBy}
        layout={layout}
        groupMode={groupMode}
        margin={{
          top: 10,
          right: 20,
          bottom: layout === "horizontal" ? 40 : 60,
          left: layout === "horizontal" ? 120 : 60,
        }}
        padding={0.3}
        colors={colors || [...COLORS.chart]}
        enableLabel={enableLabel}
        axisBottom={{
          tickSize: 5,
          tickPadding: 5,
          tickRotation: layout === "vertical" ? -45 : 0,
          legend: axisBottomLegend,
          legendPosition: "middle" as const,
          legendOffset: 50,
        }}
        axisLeft={{
          tickSize: 5,
          tickPadding: 5,
          legend: axisLeftLegend,
          legendPosition: "middle" as const,
          legendOffset: -50,
        }}
        theme={{
          background: "transparent",
          text: { fill: "#8B8B9E", fontSize: 11 },
          axis: {
            ticks: { text: { fill: "#8B8B9E", fontSize: 10 } },
            legend: { text: { fill: "#8B8B9E", fontSize: 12 } },
          },
          grid: { line: { stroke: "#3B3B4F", strokeWidth: 1 } },
          tooltip: {
            container: {
              background: "#262730",
              color: "#FAFAFA",
              fontSize: 12,
              borderRadius: 6,
              boxShadow: "0 4px 12px rgba(0,0,0,0.5)",
            },
          },
        }}
      />
    </div>
  );
}
