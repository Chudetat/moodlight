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

type BarDatum = Record<string, string | number>;

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
  colors?:
    | string[]
    | ((datum: {
        id: string | number;
        indexValue?: string | number;
        data?: Record<string, unknown>;
        [key: string]: unknown;
      }) => string);
}

export const BarChart = memo(function BarChart({
  data,
  keys,
  indexBy,
  height = 300,
  layout = "vertical",
  groupMode = "grouped",
  enableLabel = false,
  colors,
}: BarChartProps) {
  const option = useMemo(() => {
    const categories = data.map((d) => String(d[indexBy]));
    const isHorizontal = layout === "horizontal";

    const series = keys.map((key, keyIndex) => {
      const values = data.map((d) =>
        typeof d[key] === "number" ? (d[key] as number) : 0
      );

      // Pre-compute per-bar colors when colors is a function
      let colorSpec:
        | string
        | ((params: { dataIndex: number }) => string)
        | undefined;

      if (typeof colors === "function") {
        const precomputed = data.map((d) =>
          (colors as Function)({
            id: key,
            indexValue: d[indexBy],
            data: d as Record<string, unknown>,
          })
        );
        colorSpec = (params: { dataIndex: number }) =>
          precomputed[params.dataIndex];
      } else if (Array.isArray(colors)) {
        colorSpec = colors[keyIndex] || colors[0];
      } else {
        colorSpec = COLORS.chart[keyIndex % COLORS.chart.length];
      }

      return {
        name: key,
        type: "bar" as const,
        data: values,
        stack: groupMode === "stacked" ? "stack" : undefined,
        label: {
          show: enableLabel,
          color: "#FAFAFA",
          fontSize: 10,
          position: (isHorizontal ? "right" : "top") as "right" | "top",
        },
        itemStyle: {
          color: colorSpec as string,
          borderRadius: isHorizontal ? [0, 3, 3, 0] : [3, 3, 0, 0],
        },
        barMaxWidth: 40,
      };
    });

    const categoryAxis = {
      type: "category" as const,
      data: categories,
      axisLabel: {
        color: "#8B8B9E",
        fontSize: 10,
        rotate: !isHorizontal ? 45 : 0,
        width: isHorizontal ? 140 : undefined,
        overflow: "truncate" as const,
      },
      axisLine: { lineStyle: { color: "#3B3B4F" } },
      axisTick: { lineStyle: { color: "#3B3B4F" } },
    };

    const valueAxis = {
      type: "value" as const,
      axisLabel: { color: "#8B8B9E", fontSize: 10 },
      axisLine: { show: false },
      splitLine: { lineStyle: { color: "#3B3B4F", width: 1 } },
    };

    return {
      backgroundColor: "transparent",
      grid: {
        left: 10,
        right: 20,
        top: 10,
        bottom: !isHorizontal ? 60 : 30,
        containLabel: true,
      },
      tooltip: {
        trigger: "axis" as const,
        axisPointer: { type: "shadow" as const },
        backgroundColor: "#262730",
        borderColor: "#3B3B4F",
        textStyle: { color: "#FAFAFA", fontSize: 12 },
        extraCssText:
          "border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.5);",
      },
      xAxis: isHorizontal ? valueAxis : categoryAxis,
      yAxis: isHorizontal ? { ...categoryAxis, inverse: true } : valueAxis,
      series,
      animation: true,
      animationDuration: 600,
      animationEasing: "cubicOut",
    };
  }, [data, keys, indexBy, layout, groupMode, enableLabel, colors]);

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

export type { BarDatum };
