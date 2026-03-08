import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Normalize GoEmotions empathy score to 0-100 scale.
 * Must match app.py:1052-1062 exactly.
 */
export function normalizeEmpathyScore(avg: number): number {
  let score: number;
  if (avg <= 0.04) {
    score = Math.round((avg / 0.04) * 50);
  } else if (avg <= 0.10) {
    score = Math.round(50 + ((avg - 0.04) / 0.06) * 15);
  } else if (avg <= 0.30) {
    score = Math.round(65 + ((avg - 0.10) / 0.20) * 20);
  } else {
    score = Math.round(85 + ((avg - 0.30) / 0.70) * 15);
  }
  return Math.min(100, Math.max(0, score));
}

/**
 * Format a number with commas (e.g., 1234567 → "1,234,567")
 */
export function formatNumber(n: number): string {
  return new Intl.NumberFormat("en-US").format(n);
}

/**
 * Format a percentage with sign (e.g., 0.0523 → "+5.23%")
 */
export function formatPctChange(pct: number): string {
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

/**
 * Relative time string (e.g., "2 hours ago")
 */
export function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 7) return `${diffDay}d ago`;
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}
