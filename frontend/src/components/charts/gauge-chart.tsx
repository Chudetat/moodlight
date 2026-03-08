"use client";

interface GaugeChartProps {
  value: number; // 0-100
  label: string;
  size?: number;
}

export function GaugeChart({ value, label, size = 160 }: GaugeChartProps) {
  const clampedValue = Math.min(100, Math.max(0, value));
  const radius = size / 2 - 15;
  const circumference = Math.PI * radius; // half-circle
  const offset = circumference - (clampedValue / 100) * circumference;

  // Color based on value
  let color: string;
  if (clampedValue < 30) color = "#21C354";
  else if (clampedValue < 60) color = "#FACA15";
  else if (clampedValue < 80) color = "#FB923C";
  else color = "#FF4B4B";

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size / 2 + 20} viewBox={`0 0 ${size} ${size / 2 + 20}`}>
        {/* Background arc */}
        <path
          d={`M ${15} ${size / 2} A ${radius} ${radius} 0 0 1 ${size - 15} ${size / 2}`}
          fill="none"
          stroke="#3B3B4F"
          strokeWidth="12"
          strokeLinecap="round"
        />
        {/* Value arc */}
        <path
          d={`M ${15} ${size / 2} A ${radius} ${radius} 0 0 1 ${size - 15} ${size / 2}`}
          fill="none"
          stroke={color}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={`${circumference}`}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 0.5s ease" }}
        />
        {/* Value text */}
        <text
          x={size / 2}
          y={size / 2 - 5}
          textAnchor="middle"
          fill="#FAFAFA"
          fontSize="24"
          fontWeight="bold"
        >
          {Math.round(clampedValue)}
        </text>
        <text
          x={size / 2}
          y={size / 2 + 15}
          textAnchor="middle"
          fill="#8B8B9E"
          fontSize="11"
        >
          {label}
        </text>
      </svg>
    </div>
  );
}
