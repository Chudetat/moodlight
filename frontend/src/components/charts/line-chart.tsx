"use client";

import { ResponsiveLine, type DefaultSeries } from "@nivo/line";
import { COLORS } from "@/lib/constants";

interface LineChartProps {
  data: DefaultSeries[];
  height?: number;
  enableArea?: boolean;
  yFormat?: string;
  axisBottomFormat?: string;
  axisLeftFormat?: string;
  axisBottomTickValues?: string;
  axisLeftTickValues?: number;
  enablePoints?: boolean;
  curve?: "linear" | "monotoneX" | "natural" | "step";
  colors?: string[];
}

export function LineChart({
  data,
  height = 300,
  enableArea = false,
  yFormat,
  axisBottomFormat,
  axisLeftFormat,
  axisBottomTickValues,
  axisLeftTickValues,
  enablePoints = true,
  curve = "monotoneX",
  colors,
}: LineChartProps) {
  return (
    <div style={{ height }}>
      <ResponsiveLine
        data={data}
        margin={{ top: 20, right: 20, bottom: 50, left: 60 }}
        xScale={{ type: "time", format: "%Y-%m-%d", useUTC: false, precision: "day" }}
        xFormat="time:%b %d"
        yScale={{ type: "linear", min: "auto", max: "auto", stacked: false }}
        yFormat={yFormat}
        curve={curve}
        axisBottom={{
          format: axisBottomFormat || "%b %d",
          tickValues: axisBottomTickValues || "every 1 day",
          tickRotation: -45,
          tickSize: 5,
          tickPadding: 5,
        }}
        axisLeft={{
          format: axisLeftFormat,
          tickValues: axisLeftTickValues,
          tickSize: 5,
          tickPadding: 5,
        }}
        colors={colors || [...COLORS.chart]}
        lineWidth={2}
        pointSize={enablePoints ? 6 : 0}
        pointColor={{ theme: "background" }}
        pointBorderWidth={2}
        pointBorderColor={{ from: "serieColor" }}
        enableArea={enableArea}
        areaOpacity={0.1}
        useMesh={true}
        enableGridX={false}
        theme={{
          background: "transparent",
          text: { fill: "#8B8B9E", fontSize: 11 },
          axis: {
            ticks: { text: { fill: "#8B8B9E", fontSize: 10 } },
            legend: { text: { fill: "#8B8B9E" } },
          },
          grid: { line: { stroke: "#3B3B4F", strokeWidth: 1 } },
          crosshair: { line: { stroke: "#FAFAFA", strokeWidth: 1, strokeOpacity: 0.5 } },
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
