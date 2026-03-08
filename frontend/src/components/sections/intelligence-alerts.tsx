"use client";

import { useState } from "react";
import { useAuth } from "@/lib/hooks/use-auth";
import { useAlerts } from "@/lib/hooks/use-api";
import { AlertCard } from "./alert-card";
import { Button } from "@/components/ui/button";
import { CardListSkeleton } from "@/components/shared/loading-skeleton";
import { SEVERITY_ICONS } from "@/lib/constants";

const SEVERITY_FILTERS = ["all", "critical", "warning", "info", "prediction"] as const;

export function IntelligenceAlerts() {
  const { username } = useAuth();
  const [filter, setFilter] = useState<string>("all");
  const { data, isLoading } = useAlerts(username, 7);

  if (isLoading) {
    return (
      <div>
        <h2 className="mb-3 text-lg font-semibold">Intelligence Alerts</h2>
        <CardListSkeleton count={3} />
      </div>
    );
  }

  const allAlerts = data?.data ?? [];
  const filtered =
    filter === "all"
      ? allAlerts
      : allAlerts.filter((a) => a.severity === filter);

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold">
          Intelligence Alerts{" "}
          <span className="text-sm font-normal text-muted-foreground">
            ({allAlerts.length})
          </span>
        </h2>
      </div>

      {/* Severity filter tabs */}
      <div className="mb-3 flex flex-wrap gap-1.5">
        {SEVERITY_FILTERS.map((sev) => (
          <Button
            key={sev}
            variant={filter === sev ? "secondary" : "ghost"}
            size="xs"
            onClick={() => setFilter(sev)}
          >
            {sev !== "all" && (
              <span className="mr-1">{SEVERITY_ICONS[sev]}</span>
            )}
            {sev === "all"
              ? `All (${allAlerts.length})`
              : `${sev} (${allAlerts.filter((a) => a.severity === sev).length})`}
          </Button>
        ))}
      </div>

      {/* Alert list */}
      <div className="space-y-2">
        {filtered.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">
            No alerts matching this filter.
          </p>
        ) : (
          filtered.map((alert) => (
            <AlertCard key={alert.id} alert={alert} />
          ))
        )}
      </div>
    </div>
  );
}
