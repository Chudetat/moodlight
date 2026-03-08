"use client";

import Image from "next/image";
import { DashboardShell } from "@/components/layout/dashboard-shell";
import { LazySection } from "@/components/layout/lazy-section";
import { CulturalPulse } from "@/components/sections/cultural-pulse";
import { MarketSentiment } from "@/components/sections/market-sentiment";
import { EconomicIndicators } from "@/components/sections/economic-indicators";
import { CommodityPrices } from "@/components/sections/commodity-prices";
import { MoodVsMarket } from "@/components/sections/mood-vs-market";
import { PredictionMarkets } from "@/components/sections/prediction-markets";
import { IntelligenceAlerts } from "@/components/sections/intelligence-alerts";
import { CompetitiveWarRoom } from "@/components/sections/competitive-war-room";
import { TopicIntelligence } from "@/components/sections/topic-intelligence";
import {
  EmpathyByTopic,
  EmotionalBreakdown,
  EmpathyDistribution,
  TopicDistribution,
} from "@/components/sections/detailed-analysis";
import { TrendingHeadlines } from "@/components/sections/trending-headlines";
import { ViralityEmpathy } from "@/components/sections/virality-empathy";
import { VelocityLongevity } from "@/components/sections/velocity-longevity";
import { DensityScarcity } from "@/components/sections/density-scarcity";
import { BrandVLDS } from "@/components/sections/brand-vlds";
import { MoodHistory } from "@/components/sections/mood-history";
import { WorldViewTable } from "@/components/sections/world-view-table";
import { IntelDashboard } from "@/components/sections/intel-dashboard";
import { AskMoodlight } from "@/components/sections/ask-moodlight";

export default function DashboardPage() {
  return (
    <DashboardShell>
      <div className="mx-auto max-w-4xl space-y-6">
        {/* Logo + tagline */}
        <div>
          <Image
            src="/logo.png"
            alt="Moodlight"
            width={300}
            height={60}
            className="mb-1"
            priority
          />
          <p className="text-sm text-muted-foreground">
            Where culture is heading. What audiences feel. How to show up.
          </p>
        </div>

        {/* 1. Cultural Pulse */}
        <LazySection>
          <CulturalPulse />
        </LazySection>

        {/* 2. Market Sentiment */}
        <LazySection>
          <MarketSentiment />
        </LazySection>

        {/* 3. Economic Indicators */}
        <LazySection>
          <EconomicIndicators />
        </LazySection>

        {/* 4. Commodity Prices */}
        <LazySection>
          <CommodityPrices />
        </LazySection>

        {/* 5. Mood vs Market */}
        <LazySection>
          <MoodVsMarket />
        </LazySection>

        {/* 6. Prediction Markets (tier-gated) */}
        <LazySection>
          <PredictionMarkets />
        </LazySection>

        {/* 7. Intelligence Alerts */}
        <LazySection>
          <IntelligenceAlerts />
        </LazySection>

        {/* 8. Competitive War Room (tier-gated) */}
        <LazySection>
          <CompetitiveWarRoom />
        </LazySection>

        {/* 9. Topic Intelligence */}
        <LazySection>
          <TopicIntelligence />
        </LazySection>

        {/* 10. Detailed Analysis */}
        <LazySection>
          <h2 className="mb-1 text-lg font-semibold">Detailed Analysis</h2>
          <div className="grid gap-4 md:grid-cols-2">
            <EmpathyByTopic />
            <EmotionalBreakdown />
            <EmpathyDistribution />
            <TopicDistribution />
          </div>
        </LazySection>

        {/* 11. Trending Headlines */}
        <LazySection>
          <TrendingHeadlines />
        </LazySection>

        {/* 12. Virality x Empathy */}
        <LazySection>
          <ViralityEmpathy />
        </LazySection>

        {/* 13. Velocity x Longevity + Density + Scarcity */}
        <LazySection>
          <VelocityLongevity />
        </LazySection>

        <LazySection>
          <DensityScarcity />
        </LazySection>

        {/* 14. Brand VLDS */}
        <LazySection>
          <BrandVLDS />
        </LazySection>

        {/* 15. 7-Day Mood History */}
        <LazySection>
          <MoodHistory />
        </LazySection>

        {/* 16. World View */}
        <LazySection>
          <WorldViewTable />
        </LazySection>

        {/* 17. Intelligence Dashboard (tier-gated) */}
        <LazySection>
          <IntelDashboard />
        </LazySection>

        {/* 18. Ask Moodlight */}
        <LazySection>
          <AskMoodlight />
        </LazySection>
      </div>
    </DashboardShell>
  );
}
