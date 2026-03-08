"use client";

import { useAuth } from "./use-auth";
import { TIER_FEATURES } from "../constants";
import type { FeatureName } from "../types";

export function useFeatureGate(feature: FeatureName): boolean {
  const { tier } = useAuth();
  const allowedTiers = TIER_FEATURES[feature];
  if (!allowedTiers) return false;
  return allowedTiers.includes(tier);
}
