"use client";

import { ResponsiveScatterPlot } from "@nivo/scatterplot";
import { COLORS } from "@/lib/constants";

interface ScatterDataPoint {
  x: number;
  y: number;
  size?: number;
  label?: string;
}

interface ScatterSeries {
  id: string;
  data: ScatterDataPoint[];
}

interface ScatterChartProps {
  data: ScatterSeries[];
  height?: number;
  xLabel?: string;
  yLabel?: string;
  nodeSize?: number | ((d: { data: ScatterDataPoint }) => number);
  colors?: string[];
  tooltipLabel?: (point: ScatterDataPoint) => string;
}

export function ScatterChart({
  data,
  height = 350,
  xLabel,
  yLabel,
  nodeSize = 8,
  colors,
  tooltipLabel,
}: ScatterChartProps) {
  return (
    <div style={{ height }}>
      <ResponsiveScatterPlot
        data={data}
        margin={{ top: 20, right: 20, bottom: 60, left: 70 }}
        xScale={{ type: "linear", min: "auto", max: "auto" }}
        yScale={{ type: "linear", min: "auto", max: "auto" }}
        colors={colors || [...COLORS.chart]}
        nodeSize={typeof nodeSize === "function" ? nodeSize : nodeSize}
        axisBottom={{
          legend: xLabel,
          legendPosition: "middle" as const,
          legendOffset: 46,
          tickSize: 5,
          tickPadding: 5,
        }}
        axisLeft={{
          legend: yLabel,
          legendPosition: "middle" as const,
          legendOffset: -55,
          tickSize: 5,
          tickPadding: 5,
        }}
        tooltip={({ node }) => {
          const d = node.data as unknown as ScatterDataPoint;
          const text = tooltipLabel
            ? tooltipLabel(d)
            : d.label || `(${d.x}, ${d.y})`;
          return (
            <div
              style={{
                background: "#262730",
                color: "#FAFAFA",
                fontSize: 12,
                borderRadius: 6,
                padding: "8px 12px",
                maxWidth: 360,
                boxShadow: "0 4px 12px rgba(0,0,0,0.5)",
              }}
            >
              <div style={{ marginBottom: 4 }}>{text}</div>
              <div style={{ color: "#8B8B9E", fontSize: 10 }}>
                {xLabel || "X"}: {typeof d.x === "number" ? d.x.toFixed(1) : d.x}
                {" | "}
                {yLabel || "Y"}: {typeof d.y === "number" ? d.y.toFixed(1) : d.y}
              </div>
            </div>
          );
        }}
        theme={{
          background: "transparent",
          text: { fill: "#8B8B9E", fontSize: 11 },
          axis: {
            ticks: { text: { fill: "#8B8B9E", fontSize: 10 } },
            legend: { text: { fill: "#8B8B9E", fontSize: 12 } },
          },
          grid: { line: { stroke: "#3B3B4F", strokeWidth: 1 } },
        }}
      />
    </div>
  );
}

export type { ScatterSeries, ScatterDataPoint };
