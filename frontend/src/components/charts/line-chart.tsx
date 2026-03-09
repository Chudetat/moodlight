"use client";

import { memo, useMemo } from "react";
import dynamic from "next/dynamic";
import { COLORS } from "@/lib/constants";

const ReactECharts = dynamic(() => import("echarts-for-react"), {
  ssr: false,
  loading: () => (
    <div className="h-full w-full animate-pulse rounded bg-muted/10" />
  ),
});

interface LineSeriesData {
  x: string;
  y: number;
}

interface LineSeries {
  id: string;
  data: LineSeriesData[];
}

interface LineChartProps {
  data: LineSeries[];
  height?: number;
  enableArea?: boolean;
  yFormat?: string;
  axisBottomFormat?: string;
  axisLeftFormat?: string;
  axisBottomTickValues?: string;
  axisLeftTickValues?: number;
  yMin?: number | "auto";
  yMax?: number | "auto";
  enablePoints?: boolean;
  curve?: "linear" | "monotoneX" | "natural" | "step";
  colors?: string[];
}

const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

export const LineChart = memo(function LineChart({
  data,
  height = 300,
  enableArea = false,
  axisLeftFormat,
  axisLeftTickValues,
  yMin = "auto",
  yMax = "auto",
  enablePoints = true,
  curve = "monotoneX",
  colors,
}: LineChartProps) {
  const option = useMemo(() => {
    const palette = colors || [...COLORS.chart];
    const isSmooth = curve === "monotoneX" || curve === "natural";

    const series = data.map((s, i) => {
      const seriesColor = palette[i % palette.length];
      return {
        name: s.id,
        type: "line" as const,
        data: s.data.map((d) => [d.x, d.y]),
        smooth: isSmooth ? 0.4 : false,
        step: curve === "step" ? ("start" as const) : undefined,
        symbol: enablePoints ? "circle" : "none",
        symbolSize: enablePoints ? 6 : 0,
        lineStyle: { width: 2, color: seriesColor },
        itemStyle: { color: seriesColor },
        areaStyle: enableArea
          ? {
              color: {
                type: "linear" as const,
                x: 0,
                y: 0,
                x2: 0,
                y2: 1,
                colorStops: [
                  { offset: 0, color: seriesColor + "40" },
                  { offset: 1, color: seriesColor + "05" },
                ],
              },
            }
          : undefined,
      };
    });

    return {
      backgroundColor: "transparent",
      grid: { left: 60, right: 20, top: 20, bottom: 50, containLabel: false },
      tooltip: {
        trigger: "axis" as const,
        backgroundColor: "#262730",
        borderColor: "#3B3B4F",
        textStyle: { color: "#FAFAFA", fontSize: 12 },
        extraCssText:
          "border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.5);",
        axisPointer: {
          lineStyle: { color: "#FAFAFA", opacity: 0.5, width: 1 },
        },
      },
      xAxis: {
        type: "time" as const,
        axisLabel: {
          color: "#8B8B9E",
          fontSize: 10,
          rotate: 45,
          formatter: (value: number) => {
            const d = new Date(value);
            return `${MONTHS[d.getMonth()]} ${d.getDate()}`;
          },
        },
        axisLine: { lineStyle: { color: "#3B3B4F" } },
        axisTick: { lineStyle: { color: "#3B3B4F" } },
        splitLine: { show: false },
      },
      yAxis: {
        type: "value" as const,
        min: yMin === "auto" ? undefined : yMin,
        max: yMax === "auto" ? undefined : yMax,
        splitNumber: axisLeftTickValues || undefined,
        axisLabel: {
          color: "#8B8B9E",
          fontSize: 10,
          formatter: axisLeftFormat?.includes("-.0f")
            ? (v: number) => Math.round(v).toString()
            : undefined,
        },
        axisLine: { show: false },
        splitLine: { lineStyle: { color: "#3B3B4F", width: 1 } },
      },
      series,
      animation: true,
      animationDuration: 800,
      animationEasing: "cubicOut",
    };
  }, [
    data,
    enableArea,
    axisLeftFormat,
    axisLeftTickValues,
    yMin,
    yMax,
    enablePoints,
    curve,
    colors,
  ]);

  return (
    <div style={{ height }}>
      <ReactECharts
        option={option}
        style={{ height: "100%", width: "100%" }}
        opts={{ renderer: "canvas" }}
        notMerge={true}
        lazyUpdate={true}
      />
    </div>
  );
});

// Export type compatible with old Nivo DefaultSeries
export type { LineSeries as DefaultSeries };
