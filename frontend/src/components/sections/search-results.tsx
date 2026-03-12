"use client";

import { useMemo, useEffect } from "react";
import { useDashboardStore } from "@/store/dashboard-store";
import { useAuth } from "@/lib/hooks/use-auth";
import {
  useCombinedData,
  useAlerts,
  useBrandVLDS,
  useBrandStocks,
} from "@/lib/hooks/use-api";
import { normalizeEmpathyScore } from "@/lib/utils";
import { MetricCard } from "@/components/charts/metric-card";
import { Badge } from "@/components/ui/badge";
import { SEVERITY_ICONS } from "@/lib/constants";

// Known brand → ticker mappings (matches backend signal_log_tracker)
const BRAND_TICKERS: Record<string, string> = {
  nvidia: "NVDA",
  amazon: "AMZN",
  disney: "DIS",
  "lockheed martin": "LMT",
  apple: "AAPL",
  google: "GOOGL",
  alphabet: "GOOGL",
  microsoft: "MSFT",
  meta: "META",
  facebook: "META",
  tesla: "TSLA",
  netflix: "NFLX",
  intel: "INTC",
  amd: "AMD",
  nike: "NKE",
  walmart: "WMT",
  "under armour": "UA",
  adidas: "ADDYY",
  "coca-cola": "KO",
  pepsi: "PEP",
  boeing: "BA",
  "jp morgan": "JPM",
  "goldman sachs": "GS",
  "morgan stanley": "MS",
  oracle: "ORCL",
  ibm: "IBM",
  salesforce: "CRM",
  uber: "UBER",
  airbnb: "ABNB",
  spotify: "SPOT",
  snap: "SNAP",
  snapchat: "SNAP",
  twitter: "X",
  ebay: "EBAY",
  paypal: "PYPL",
  block: "XYZ",
  square: "XYZ",
};

function lookupTicker(query: string): string | null {
  const q = query.toLowerCase().trim();
  // Direct match
  if (BRAND_TICKERS[q]) return BRAND_TICKERS[q];
  // Partial match (e.g., "under armour" in "under armour inc")
  for (const [brand, ticker] of Object.entries(BRAND_TICKERS)) {
    if (q.includes(brand) || brand.includes(q)) return ticker;
  }
  return null;
}

export function SearchResults() {
  const searchQuery = useDashboardStore((s) => s.searchQuery);
  const setFocusedBrand = useDashboardStore((s) => s.setFocusedBrand);
  const days = useDashboardStore((s) => s.days);
  const { username } = useAuth();
  const { data: combinedData } = useCombinedData(days);
  const { data: alertsData } = useAlerts(username, 7);

  const q = searchQuery.trim().toLowerCase();
  const ticker = q ? lookupTicker(q) : null;

  // Fetch VLDS and stock data for the searched brand
  const { data: vldsData } = useBrandVLDS(q || "");
  const { data: stockData } = useBrandStocks(ticker || "", 2);

  // Set focusedBrand so the Brand VLDS section also activates
  useEffect(() => {
    if (q) {
      setFocusedBrand(searchQuery.trim());
    }
    // Only clear focusedBrand if search was explicitly cleared (not on unmount)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const { headlines, alerts, mentionCount, emotions, topTopics } =
    useMemo(() => {
      if (!q)
        return {
          headlines: [],
          alerts: [],
          mentionCount: 0,
          emotions: [] as { emotion: string; count: number; pct: number }[],
          topTopics: [] as { topic: string; count: number }[],
        };

      // Match headlines/posts
      const allItems = combinedData?.data ?? [];
      const matched = allItems.filter(
        (d) =>
          d.text &&
          (d.text.toLowerCase().includes(q) ||
            (d.topic && d.topic.toLowerCase().includes(q)))
      );

      const matchedHeadlines = [...matched]
        .sort((a, b) => b.intensity - a.intensity)
        .slice(0, 8);

      // Emotion breakdown
      const emotionMap = new Map<string, number>();
      for (const item of matched) {
        if (item.emotion_top_1) {
          emotionMap.set(
            item.emotion_top_1,
            (emotionMap.get(item.emotion_top_1) || 0) + 1
          );
        }
      }
      const emotionList = Array.from(emotionMap.entries())
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5)
        .map(([emotion, count]) => ({
          emotion,
          count,
          pct: Math.round((count / matched.length) * 100),
        }));

      // Topic breakdown
      const topicMap = new Map<string, number>();
      for (const item of matched) {
        if (item.topic) {
          topicMap.set(item.topic, (topicMap.get(item.topic) || 0) + 1);
        }
      }
      const topicList = Array.from(topicMap.entries())
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5)
        .map(([topic, count]) => ({ topic, count }));

      // Match alerts
      const allAlerts = alertsData?.data ?? [];
      const matchedAlerts = allAlerts
        .filter((a) =>
          [a.title, a.summary, a.description, a.brand, a.brand_name, a.topic]
            .filter(Boolean)
            .some((field) => String(field).toLowerCase().includes(q))
        )
        .slice(0, 5);

      return {
        headlines: matchedHeadlines,
        alerts: matchedAlerts,
        mentionCount: matched.length,
        emotions: emotionList,
        topTopics: topicList,
      };
    }, [q, combinedData, alertsData]);

  if (!q) return null;

  const vlds = vldsData?.vlds;
  const stock = stockData?.data;
  const latestStock =
    stock && stock.length > 0 ? stock[0] : null;

  return (
    <div className="space-y-4 rounded-lg border border-primary/30 bg-primary/5 p-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">
          Dashboard Focus: &ldquo;{searchQuery.trim()}&rdquo;
        </h2>
        <div className="flex gap-2">
          {ticker && (
            <Badge className="bg-blue-600 text-xs text-white">{ticker}</Badge>
          )}
          <Badge variant="secondary" className="text-xs">
            {mentionCount} mention{mentionCount !== 1 ? "s" : ""}
          </Badge>
        </div>
      </div>

      {mentionCount === 0 && !vlds ? (
        <p className="py-2 text-sm text-muted-foreground">
          No mentions found for &ldquo;{searchQuery.trim()}&rdquo; in the last{" "}
          {days} days. Try a broader term or check back soon.
        </p>
      ) : (
        <>
          {/* Row 1: Key metrics */}
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <MetricCard label="Mentions" value={mentionCount} />
            {vlds && (
              <>
                <MetricCard
                  label="Velocity"
                  value={`${Math.round((vlds.velocity ?? 0) * 100)}%`}
                  sublabel={vlds.velocity_label || ""}
                />
                <MetricCard
                  label="Density"
                  value={`${Math.round((vlds.density ?? 0) * 100)}%`}
                  sublabel={vlds.density_label || ""}
                />
                <MetricCard
                  label="Empathy"
                  value={vlds.empathy_label || "N/A"}
                />
              </>
            )}
          </div>

          {/* Row 2: Stock data (if publicly traded) */}
          {ticker && latestStock && (
            <div className="rounded border border-border bg-card p-3">
              <p className="mb-2 text-xs font-medium uppercase text-muted-foreground">
                Stock Performance ({ticker})
              </p>
              <div className="grid grid-cols-4 gap-3 text-center text-sm">
                <div>
                  <div className="text-muted-foreground text-xs">Close</div>
                  <div className="font-semibold">
                    ${latestStock.close.toFixed(2)}
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground text-xs">High</div>
                  <div className="font-semibold">
                    ${latestStock.high.toFixed(2)}
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground text-xs">Low</div>
                  <div className="font-semibold">
                    ${latestStock.low.toFixed(2)}
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground text-xs">Volume</div>
                  <div className="font-semibold text-xs">
                    {latestStock.volume.toLocaleString()}
                  </div>
                </div>
              </div>
            </div>
          )}
          {ticker && !latestStock && (
            <p className="text-xs text-muted-foreground">
              {ticker} stock data not available in database.
              {" "}Only watchlisted brand stocks are tracked.
            </p>
          )}

          {/* Row 3: Emotions + Topics side by side */}
          {(emotions.length > 0 || topTopics.length > 0) && (
            <div className="grid gap-3 md:grid-cols-2">
              {emotions.length > 0 && (
                <div className="rounded border border-border bg-card p-3">
                  <p className="mb-1.5 text-xs font-medium uppercase text-muted-foreground">
                    Emotion Breakdown
                  </p>
                  <div className="space-y-1">
                    {emotions.map((e) => (
                      <div
                        key={e.emotion}
                        className="flex items-center justify-between text-xs"
                      >
                        <span className="capitalize">{e.emotion}</span>
                        <span className="text-muted-foreground">
                          {e.count} ({e.pct}%)
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {topTopics.length > 0 && (
                <div className="rounded border border-border bg-card p-3">
                  <p className="mb-1.5 text-xs font-medium uppercase text-muted-foreground">
                    Top Narratives
                  </p>
                  <div className="space-y-1">
                    {topTopics.map((t) => (
                      <div
                        key={t.topic}
                        className="flex items-center justify-between text-xs"
                      >
                        <span>{t.topic}</span>
                        <span className="text-muted-foreground">
                          {t.count} posts
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Row 4: Alerts */}
          {alerts.length > 0 && (
            <div>
              <p className="mb-1.5 text-xs font-medium uppercase text-muted-foreground">
                Intelligence Alerts ({alerts.length})
              </p>
              <div className="space-y-1">
                {alerts.map((a) => (
                  <div
                    key={a.id}
                    className="rounded border border-border bg-card p-2 text-sm"
                  >
                    <span className="mr-1">
                      {SEVERITY_ICONS[a.severity] ?? "\uD83D\uDD35"}
                    </span>
                    <span className="font-medium">{a.title}</span>
                    {(a.brand || a.brand_name) && (
                      <Badge variant="outline" className="ml-2 text-[10px]">
                        {a.brand_name || a.brand}
                      </Badge>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Row 5: Headlines */}
          {headlines.length > 0 && (
            <div>
              <p className="mb-1.5 text-xs font-medium uppercase text-muted-foreground">
                Top Headlines ({headlines.length})
              </p>
              <div className="space-y-1">
                {headlines.map((h, i) => {
                  const empathy = normalizeEmpathyScore(h.empathy_score);
                  const date = new Date(h.created_at);
                  const dateStr = `${date.getMonth() + 1}/${date.getDate()}`;
                  return (
                    <div
                      key={i}
                      className="rounded border border-border bg-card p-2"
                    >
                      <p className="text-sm">{h.text.slice(0, 300)}</p>
                      <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
                        <span>{dateStr}</span>
                        <span>Intensity: {h.intensity}</span>
                        <span>Empathy: {empathy}</span>
                        {h.topic && <span>{h.topic}</span>}
                        <span className="capitalize">
                          {h._source_table === "social_scored"
                            ? "social"
                            : "news"}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
