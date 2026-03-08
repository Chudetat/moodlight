import { Card, CardContent } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";
import { Lock } from "lucide-react";
import type { FeatureName } from "@/lib/types";

const FEATURE_LABELS: Record<FeatureName, string> = {
  competitive_war_room: "Competitive War Room",
  intelligence_reports: "Intelligence Reports",
  ask_moodlight: "Ask Moodlight",
  intelligence_dashboard: "Intelligence Dashboard",
  prediction_markets: "Prediction Markets",
  strategic_brief: "Strategic Brief",
  brand_watchlist: "Brand Watchlist",
  topic_watchlist: "Topic Watchlist",
  brand_focus: "Brand Focus",
  competitive_tracking: "Competitive Tracking",
};

export function UpgradePrompt({ feature }: { feature: FeatureName }) {
  const label = FEATURE_LABELS[feature] || feature;

  return (
    <Card className="border-dashed">
      <CardContent className="flex flex-col items-center gap-3 py-8 text-center">
        <Lock className="h-8 w-8 text-muted-foreground" />
        <div>
          <p className="font-medium">{label}</p>
          <p className="text-sm text-muted-foreground">
            Upgrade your plan to unlock this feature.
          </p>
        </div>
        <a
          href="https://moodlightintel.com/#pricing"
          className={buttonVariants({ variant: "outline", size: "sm" })}
        >
          View Plans
        </a>
      </CardContent>
    </Card>
  );
}
