"use client";

import type { ReactNode } from "react";
import { useFeatureGate } from "@/lib/hooks/use-feature-gate";
import type { FeatureName } from "@/lib/types";
import { UpgradePrompt } from "./upgrade-prompt";

interface FeatureGateProps {
  feature: FeatureName;
  children: ReactNode;
}

export function FeatureGate({ feature, children }: FeatureGateProps) {
  const hasAccess = useFeatureGate(feature);

  if (!hasAccess) {
    return <UpgradePrompt feature={feature} />;
  }

  return <>{children}</>;
}
