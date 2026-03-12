"use client";

import { useState, useCallback, useMemo } from "react";
import { useAuth } from "@/lib/hooks/use-auth";
import { useDashboardStore } from "@/store/dashboard-store";
import { useAlerts, useAlertPreferences } from "@/lib/hooks/use-api";
import { AlertCard } from "./alert-card";
import { Button } from "@/components/ui/button";
import { CardListSkeleton } from "@/components/shared/loading-skeleton";
import { SEVERITY_ICONS } from "@/lib/constants";

const SEVERITY_FILTERS = [
  "all",
  "critical",
  "warning",
  "info",
  "prediction",
] as const;
type SeverityFilter = (typeof SEVERITY_FILTERS)[number];
const PAGE_SIZE = 20;

export function IntelligenceAlerts() {
  const { username } = useAuth();
  const searchQuery = useDashboardStore((s) => s.searchQuery);
  const [filter, setFilter] = useState<SeverityFilter>("all");
  const [showCount, setShowCount] = useState(PAGE_SIZE);
  const { data, isLoading } = useAlerts(username, 7);
  const { data: prefsData } = useAlertPreferences();

  // Filter by user alert preferences, search query, and sort
  const { prefFiltered, sorted } = useMemo(() => {
    const allAlerts = data?.data ?? [];
    const prefs = prefsData?.preferences;
    let pf = prefs
      ? allAlerts.filter((a) => {
          const pref = prefs[a.alert_type];
          return pref === undefined || pref.enabled;
        })
      : allAlerts;

    // Apply search query filter
    const q = searchQuery.trim().toLowerCase();
    if (q) {
      pf = pf.filter((a) =>
        [a.title, a.summary, a.description, a.brand, a.brand_name, a.topic, a.alert_type]
          .filter(Boolean)
          .some((field) => String(field).toLowerCase().includes(q))
      );
    }

    // Sort: unread first, then by timestamp descending
    const s = [...pf].sort((a, b) => {
      if (a.is_read !== b.is_read) return a.is_read ? 1 : -1;
      return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
    });

    return { prefFiltered: pf, sorted: s };
  }, [data, prefsData, searchQuery]);

  const isPrediction = (a: { alert_type: string }) =>
    a.alert_type.startsWith("predictive_");

  // Severity filter + pagination
  const { filtered, unreadCount, visible, hasMore } = useMemo(() => {
    const f =
      filter === "all"
        ? sorted
        : filter === "prediction"
          ? sorted.filter(isPrediction)
          : sorted.filter((a) => a.severity === filter);
    const uc = prefFiltered.filter((a) => !a.is_read).length;
    const v = f.slice(0, showCount);
    const hm = f.length > showCount;
    return { filtered: f, unreadCount: uc, visible: v, hasMore: hm };
  }, [sorted, prefFiltered, filter, showCount]);

  const handleFilterChange = (f: SeverityFilter) => {
    setFilter(f);
    setShowCount(PAGE_SIZE);
  };

  const handleExport = useCallback(() => {
    if (filtered.length === 0) return;
    const headers = [
      "ID",
      "Timestamp",
      "Type",
      "Severity",
      "Title",
      "Description",
      "Recommendation",
      "Confidence",
      "Brand",
      "Topic",
      "Investigation",
    ];
    const csvRows = filtered.map((al) =>
      [
        al.id,
        al.timestamp,
        al.alert_type,
        al.severity,
        al.title,
        al.description || al.summary,
        al.recommendation ?? "",
        al.confidence ?? "",
        al.brand_name || al.brand || "",
        al.topic ?? "",
        al.investigation ? JSON.stringify(al.investigation) : "",
      ]
        .map((v) => `"${String(v).replace(/"/g, '""')}"`)
        .join(",")
    );
    const csv = [headers.join(","), ...csvRows].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "moodlight_alerts.csv";
    anchor.click();
    URL.revokeObjectURL(url);
  }, [filtered]);

  if (isLoading) {
    return (
      <div>
        <h2 className="mb-1 text-lg font-semibold">Intelligence Alerts</h2>
        <CardListSkeleton count={3} />
      </div>
    );
  }

  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <h2 className="text-lg font-semibold">
          Intelligence Alerts{" "}
          <span className="text-sm font-normal text-muted-foreground">
            ({filtered.length})
          </span>
          {unreadCount > 0 && (
            <span className="ml-1.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
              {unreadCount}
            </span>
          )}
        </h2>
        {filtered.length > 0 && (
          <Button
            variant="outline"
            size="sm"
            className="text-xs"
            onClick={handleExport}
          >
            Export CSV
          </Button>
        )}
      </div>
      <p className="mb-3 text-xs text-muted-foreground">
        Autonomous anomaly detection &mdash; Moodlight watches so you
        don&apos;t have to.
      </p>

      {/* Severity filter tabs */}
      <div className="mb-3 flex flex-wrap gap-1.5">
        {SEVERITY_FILTERS.map((sev) => {
          const count =
            sev === "all"
              ? prefFiltered.length
              : sev === "prediction"
                ? prefFiltered.filter(isPrediction).length
                : prefFiltered.filter((a) => a.severity === sev).length;
          return (
            <button
              key={sev}
              onClick={() => handleFilterChange(sev)}
              className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                filter === sev
                  ? "bg-primary/20 text-primary"
                  : "text-muted-foreground hover:bg-muted"
              }`}
            >
              {sev !== "all" && (
                <span className="mr-1">{SEVERITY_ICONS[sev]}</span>
              )}
              {sev === "all"
                ? `All (${count})`
                : `${sev.charAt(0).toUpperCase() + sev.slice(1)} (${count})`}
            </button>
          );
        })}
      </div>

      {/* Alert list */}
      <div className="space-y-2">
        {visible.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">
            {filter === "all"
              ? "No recent alerts."
              : `No ${filter} alerts.`}
          </p>
        ) : (
          visible.map((alert) => (
            <AlertCard key={alert.id} alert={alert} />
          ))
        )}
      </div>

      {/* Show more */}
      {hasMore && (
        <div className="mt-3 text-center">
          <Button
            variant="ghost"
            size="sm"
            className="w-full text-xs text-muted-foreground"
            onClick={() => setShowCount((c) => c + PAGE_SIZE)}
          >
            Show more ({filtered.length - showCount} remaining)
          </Button>
        </div>
      )}
    </div>
  );
}
