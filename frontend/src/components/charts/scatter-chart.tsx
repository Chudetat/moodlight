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

export const ScatterChart = memo(function ScatterChart({
  data,
  height = 350,
  xLabel,
  yLabel,
  nodeSize = 8,
  colors,
  tooltipLabel,
}: ScatterChartProps) {
  const option = useMemo(() => {
    const palette = colors || [...COLORS.chart];

    const series = data.map((s, i) => ({
      name: s.id,
      type: "scatter" as const,
      data: s.data.map((d) => ({
        value: [d.x, d.y],
        _size: d.size,
        _label: d.label,
        _raw: d,
      })),
      symbolSize:
        typeof nodeSize === "function"
          ? (item: { _size?: number; _raw: ScatterDataPoint }) =>
              nodeSize({ data: item._raw })
          : (item: { _size?: number }) => item._size || nodeSize,
      itemStyle: {
        color: palette[i % palette.length],
        opacity: 0.8,
      },
      emphasis: {
        itemStyle: { opacity: 1, borderColor: "#fff", borderWidth: 1 },
      },
    }));

    return {
      backgroundColor: "transparent",
      grid: {
        left: 70,
        right: 20,
        top: 20,
        bottom: 60,
        containLabel: false,
      },
      tooltip: {
        trigger: "item" as const,
        backgroundColor: "#262730",
        borderColor: "#3B3B4F",
        textStyle: { color: "#FAFAFA", fontSize: 12 },
        extraCssText:
          "border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.5); max-width: 600px; min-width: 300px; white-space: normal;",
        formatter: (params: {
          data: {
            value: [number, number];
            _label?: string;
            _raw: ScatterDataPoint;
          };
        }) => {
          const raw = params.data._raw;
          const text = tooltipLabel
            ? tooltipLabel(raw)
            : raw.label || `(${raw.x}, ${raw.y})`;
          const xVal =
            typeof raw.x === "number" ? raw.x.toFixed(1) : String(raw.x);
          const yVal =
            typeof raw.y === "number" ? raw.y.toFixed(1) : String(raw.y);
          return `<div style="margin-bottom:4px;line-height:1.4">${text}</div><div style="color:#8B8B9E;font-size:10px">${xLabel || "X"}: ${xVal} | ${yLabel || "Y"}: ${yVal}</div>`;
        },
      },
      xAxis: {
        type: "value" as const,
        name: xLabel,
        nameLocation: "middle" as const,
        nameGap: 35,
        nameTextStyle: { color: "#8B8B9E", fontSize: 12 },
        axisLabel: { color: "#8B8B9E", fontSize: 10 },
        axisLine: { lineStyle: { color: "#3B3B4F" } },
        splitLine: { lineStyle: { color: "#3B3B4F", width: 1 } },
      },
      yAxis: {
        type: "value" as const,
        name: yLabel,
        nameLocation: "middle" as const,
        nameGap: 50,
        nameTextStyle: { color: "#8B8B9E", fontSize: 12 },
        axisLabel: { color: "#8B8B9E", fontSize: 10 },
        axisLine: { show: false },
        splitLine: { lineStyle: { color: "#3B3B4F", width: 1 } },
      },
      series,
      animation: true,
      animationDuration: 600,
      animationEasing: "cubicOut",
    };
  }, [data, xLabel, yLabel, nodeSize, colors, tooltipLabel]);

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

export type { ScatterSeries, ScatterDataPoint };
