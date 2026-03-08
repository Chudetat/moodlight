"use client";

import { LazySection } from "@/components/layout/lazy-section";
import { CulturalPulse } from "@/components/sections/cultural-pulse";
import { MarketSentiment } from "@/components/sections/market-sentiment";
import { EconomicIndicators } from "@/components/sections/economic-indicators";
import { CommodityPrices } from "@/components/sections/commodity-prices";
import { MoodHistory } from "@/components/sections/mood-history";
import { IntelligenceAlerts } from "@/components/sections/intelligence-alerts";
import { TopicIntelligence } from "@/components/sections/topic-intelligence";
import { CompetitiveWarRoom } from "@/components/sections/competitive-war-room";
import { IntelDashboard } from "@/components/sections/intel-dashboard";
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
import { MoodVsMarket } from "@/components/sections/mood-vs-market";
import { BrandVLDS } from "@/components/sections/brand-vlds";
import { AskMoodlight } from "@/components/sections/ask-moodlight";
import { WorldViewTable } from "@/components/sections/world-view-table";

export default function DashboardPage() {
  return (
    <div className="mx-auto max-w-7xl space-y-6">
      {/* Phase 2B — Above the fold */}
      <LazySection>
        <CulturalPulse />
      </LazySection>

      <LazySection>
        <MarketSentiment />
      </LazySection>

      <LazySection>
        <EconomicIndicators />
      </LazySection>

      <LazySection>
        <CommodityPrices />
      </LazySection>

      <LazySection>
        <MoodHistory />
      </LazySection>

      {/* Phase 2C — Intelligence & Alerts */}
      <LazySection>
        <IntelligenceAlerts />
      </LazySection>

      <LazySection>
        <TopicIntelligence />
      </LazySection>

      <LazySection>
        <CompetitiveWarRoom />
      </LazySection>

      <LazySection>
        <IntelDashboard />
      </LazySection>

      {/* Phase 2D — Analysis & Visualization */}
      <LazySection>
        <h2 className="mb-3 text-lg font-semibold">Detailed Analysis</h2>
        <div className="grid gap-4 md:grid-cols-2">
          <EmpathyByTopic />
          <EmotionalBreakdown />
          <EmpathyDistribution />
          <TopicDistribution />
        </div>
      </LazySection>

      <LazySection>
        <TrendingHeadlines />
      </LazySection>

      <LazySection>
        <ViralityEmpathy />
      </LazySection>

      <LazySection>
        <VelocityLongevity />
      </LazySection>

      <LazySection>
        <DensityScarcity />
      </LazySection>

      {/* Phase 2E — Interactive features */}
      <LazySection>
        <MoodVsMarket />
      </LazySection>

      <LazySection>
        <BrandVLDS />
      </LazySection>

      <LazySection>
        <AskMoodlight />
      </LazySection>

      <LazySection>
        <WorldViewTable />
      </LazySection>
    </div>
  );
}
