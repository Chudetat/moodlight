"use client";

const ZONES = [
  { label: "Low", min: 0, max: 1.5, color: "#90EE90" },
  { label: "Moderate", min: 1.5, max: 2.5, color: "#FFFF00" },
  { label: "Elevated", min: 2.5, max: 3.5, color: "#FFA500" },
  { label: "Critical", min: 3.5, max: 5.0, color: "#FF0000" },
];

interface GaugeChartProps {
  value: number; // 0-5 scale (raw intensity)
  label: string;
  size?: number;
}

export function GaugeChart({ value, label, size = 180 }: GaugeChartProps) {
  const clampedValue = Math.min(5, Math.max(0, value));
  const zone = ZONES.find((z) => clampedValue >= z.min && clampedValue < z.max) || ZONES[3];
  const pct = clampedValue / 5; // 0-1 for arc drawing
  const radius = size / 2 - 15;
  const circumference = Math.PI * radius;
  const offset = circumference - pct * circumference;

  return (
    <div className="flex flex-col items-center">
      <svg
        width={size}
        height={size / 2 + 30}
        viewBox={`0 0 ${size} ${size / 2 + 30}`}
      >
        {/* Background zone arcs */}
        {ZONES.map((z) => {
          const startPct = z.min / 5;
          const endPct = z.max / 5;
          const startAngle = Math.PI * (1 - startPct);
          const endAngle = Math.PI * (1 - endPct);
          const cx = size / 2;
          const cy = size / 2;
          const x1 = cx + radius * Math.cos(startAngle);
          const y1 = cy - radius * Math.sin(startAngle);
          const x2 = cx + radius * Math.cos(endAngle);
          const y2 = cy - radius * Math.sin(endAngle);
          return (
            <path
              key={z.label}
              d={`M ${x1} ${y1} A ${radius} ${radius} 0 0 1 ${x2} ${y2}`}
              fill="none"
              stroke={z.color}
              strokeWidth="14"
              strokeLinecap="butt"
              opacity={0.3}
            />
          );
        })}
        {/* Active arc */}
        <path
          d={`M ${15} ${size / 2} A ${radius} ${radius} 0 0 1 ${size - 15} ${size / 2}`}
          fill="none"
          stroke={zone.color}
          strokeWidth="14"
          strokeLinecap="round"
          strokeDasharray={`${circumference}`}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 0.5s ease" }}
        />
        {/* Value text */}
        <text
          x={size / 2}
          y={size / 2 - 8}
          textAnchor="middle"
          fill="#FAFAFA"
          fontSize="22"
          fontWeight="bold"
        >
          {clampedValue.toFixed(2)}
        </text>
        <text
          x={size / 2}
          y={size / 2 + 10}
          textAnchor="middle"
          fill={zone.color}
          fontSize="12"
          fontWeight="600"
        >
          {zone.label}
        </text>
        <text
          x={size / 2}
          y={size / 2 + 25}
          textAnchor="middle"
          fill="#8B8B9E"
          fontSize="10"
        >
          {label} (0-5)
        </text>
      </svg>
    </div>
  );
}
