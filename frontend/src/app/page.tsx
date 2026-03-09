"use client";

import Image from "next/image";
import { DashboardShell } from "@/components/layout/dashboard-shell";
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
import { BrandComparison } from "@/components/sections/brand-comparison";
import { MoodHistory } from "@/components/sections/mood-history";
import { WorldViewTable } from "@/components/sections/world-view-table";
import { IntelDashboard } from "@/components/sections/intel-dashboard";
import { HistoricalTrends } from "@/components/sections/historical-trends";
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
        <CulturalPulse />

        {/* 2. Market Sentiment */}
        <MarketSentiment />

        {/* 3. Economic Indicators */}
        <EconomicIndicators />

        {/* 4. Commodity Prices */}
        <CommodityPrices />

        {/* 5. Mood vs Market */}
        <section style={{ contentVisibility: "auto", containIntrinsicSize: "auto 400px" }}>
          <MoodVsMarket />
        </section>

        {/* 6. Prediction Markets (tier-gated) */}
        <section style={{ contentVisibility: "auto", containIntrinsicSize: "auto 300px" }}>
          <PredictionMarkets />
        </section>

        {/* 7. Intelligence Alerts */}
        <section style={{ contentVisibility: "auto", containIntrinsicSize: "auto 600px" }}>
          <IntelligenceAlerts />
        </section>

        {/* 8. Competitive War Room (tier-gated) */}
        <section style={{ contentVisibility: "auto", containIntrinsicSize: "auto 400px" }}>
          <CompetitiveWarRoom />
        </section>

        {/* 9. Topic Intelligence */}
        <section style={{ contentVisibility: "auto", containIntrinsicSize: "auto 500px" }}>
          <TopicIntelligence />
        </section>

        {/* 10. Detailed Analysis */}
        <section style={{ contentVisibility: "auto", containIntrinsicSize: "auto 700px" }}>
          <div>
            <h2 className="mb-1 text-lg font-semibold">Detailed Analysis</h2>
            <div className="grid gap-4 md:grid-cols-2">
              <EmpathyByTopic />
              <EmotionalBreakdown />
              <EmpathyDistribution />
              <TopicDistribution />
            </div>
          </div>
        </section>

        {/* 11. Trending Headlines */}
        <section style={{ contentVisibility: "auto", containIntrinsicSize: "auto 400px" }}>
          <TrendingHeadlines />
        </section>

        {/* 12. Virality x Empathy */}
        <section style={{ contentVisibility: "auto", containIntrinsicSize: "auto 400px" }}>
          <ViralityEmpathy />
        </section>

        {/* 13. Velocity x Longevity + Density + Scarcity */}
        <section style={{ contentVisibility: "auto", containIntrinsicSize: "auto 400px" }}>
          <VelocityLongevity />
        </section>
        <section style={{ contentVisibility: "auto", containIntrinsicSize: "auto 400px" }}>
          <DensityScarcity />
        </section>

        {/* 14. Brand VLDS */}
        <section style={{ contentVisibility: "auto", containIntrinsicSize: "auto 400px" }}>
          <BrandVLDS />
        </section>

        {/* 14b. Brand Comparison */}
        <section style={{ contentVisibility: "auto", containIntrinsicSize: "auto 300px" }}>
          <BrandComparison />
        </section>

        {/* 15. 7-Day Mood History */}
        <section style={{ contentVisibility: "auto", containIntrinsicSize: "auto 400px" }}>
          <MoodHistory />
        </section>

        {/* 16. World View */}
        <section style={{ contentVisibility: "auto", containIntrinsicSize: "auto 500px" }}>
          <WorldViewTable />
        </section>

        {/* 17. Intelligence Dashboard (tier-gated) */}
        <section style={{ contentVisibility: "auto", containIntrinsicSize: "auto 600px" }}>
          <IntelDashboard />
        </section>

        {/* 18. Historical Trends (shows only when time range > 7d) */}
        <section style={{ contentVisibility: "auto", containIntrinsicSize: "auto 400px" }}>
          <HistoricalTrends />
        </section>

        {/* 19. Ask Moodlight */}
        <AskMoodlight />
      </div>
    </DashboardShell>
  );
}
