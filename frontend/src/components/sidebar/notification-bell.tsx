"use client";

import { useState } from "react";
import { useAuth } from "@/lib/hooks/use-auth";
import { useAlerts, useMarkAllAlertsRead, useMarkAlertRead } from "@/lib/hooks/use-api";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SEVERITY_ICONS, ALERT_TYPE_CATEGORIES } from "@/lib/constants";

export function NotificationBell() {
  const { username } = useAuth();
  const { data } = useAlerts(username);
  const markAll = useMarkAllAlertsRead();
  const markRead = useMarkAlertRead();
  const [severityFilter, setSeverityFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");

  if (!username) return null;
  const allAlerts = data?.data ?? [];
  const unread = allAlerts.filter((a) => !a.is_read).length;

  let filtered = allAlerts;
  if (severityFilter !== "all") {
    filtered = filtered.filter((a) => a.severity === severityFilter);
  }
  if (typeFilter !== "all") {
    const typeList = ALERT_TYPE_CATEGORIES[typeFilter] ?? [];
    if (typeList.length > 0) {
      const typeSet = new Set(typeList);
      filtered = filtered.filter((a) => typeSet.has(a.alert_type));
    }
  }
  const displayed = filtered.slice(0, 15);

  return (
    <div className="space-y-2">
      <p className="text-xs font-medium uppercase text-muted-foreground">
        Alerts{unread > 0 ? ` (${unread})` : ""}
      </p>

      <div className="flex gap-2">
        <Select value={severityFilter} onValueChange={(v) => v && setSeverityFilter(v)}>
          <SelectTrigger className="h-7 text-xs">
            <SelectValue placeholder="Severity" />
          </SelectTrigger>
          <SelectContent>
            {["all", "critical", "warning", "info"].map((s) => (
              <SelectItem key={s} value={s}>
                {s === "all" ? "All severities" : s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={typeFilter} onValueChange={(v) => v && setTypeFilter(v)}>
          <SelectTrigger className="h-7 text-xs">
            <SelectValue placeholder="Type" />
          </SelectTrigger>
          <SelectContent>
            {["all", "brand", "topic", "global", "predictive", "competitive"].map((t) => (
              <SelectItem key={t} value={t}>
                {t === "all" ? "All types" : t}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {unread > 0 && (
        <Button
          variant="ghost"
          size="sm"
          className="w-full text-xs"
          onClick={() => markAll.mutate()}
        >
          Mark all as read
        </Button>
      )}

      <div className="max-h-64 space-y-1 overflow-y-auto">
        {displayed.length === 0 && (
          <p className="text-xs text-muted-foreground">No alerts match filters.</p>
        )}
        {displayed.map((a) => {
          const icon = SEVERITY_ICONS[a.severity] ?? "\uD83D\uDD35";
          return (
            <div
              key={a.id}
              className="cursor-pointer rounded px-1 py-0.5 text-xs hover:bg-muted/50"
              onClick={() => {
                if (!a.is_read) markRead.mutate(a.id);
              }}
            >
              <div>
                {icon} {!a.is_read && <span className="font-bold">NEW </span>}
                {a.title}
              </div>
              {a.description && (
                <div className="pl-5 text-[10px] text-muted-foreground">
                  {String(a.description).slice(0, 120)}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
