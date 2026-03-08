"use client";

import { useState } from "react";
import { useAuth } from "@/lib/hooks/use-auth";
import { usePipelineHealth } from "@/lib/hooks/use-api";
import { DashboardShell } from "@/components/layout/dashboard-shell";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { MetricCard } from "@/components/charts/metric-card";
import { redirect } from "next/navigation";
import type { Customer, AdminAnalytics } from "@/lib/types";

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`/api/proxy${path}`);
  if (!res.ok) throw new Error("Failed to fetch");
  return res.json();
}

function Customers() {
  const queryClient = useQueryClient();
  const { data } = useQuery<{ customers: Customer[] }>({
    queryKey: ["admin-customers"],
    queryFn: () => apiFetch("/api/admin/customers"),
  });
  const [search, setSearch] = useState("");

  const customers = (data?.customers ?? []).filter(
    (c) =>
      c.email.toLowerCase().includes(search.toLowerCase()) ||
      c.username.toLowerCase().includes(search.toLowerCase())
  );

  async function deleteCustomer(username: string) {
    if (!confirm(`Delete customer ${username}?`)) return;
    await fetch(`/api/proxy/api/admin/customers/${username}`, {
      method: "DELETE",
    });
    queryClient.invalidateQueries({ queryKey: ["admin-customers"] });
  }

  return (
    <div className="space-y-3">
      <h3 className="text-base font-semibold">Customers ({data?.customers?.length ?? 0})</h3>
      <Input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search by email or username..."
        className="h-8 text-xs"
      />
      <div className="max-h-64 space-y-2 overflow-y-auto">
        {customers.map((c) => (
          <Card key={c.username}>
            <CardContent className="flex items-center justify-between p-3">
              <div>
                <p className="text-sm font-medium">{c.username}</p>
                <p className="text-xs text-muted-foreground">{c.email}</p>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className="text-[10px] capitalize">
                  {c.tier}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {c.brief_credits} credits
                </span>
                <Button
                  variant="ghost"
                  size="xs"
                  className="text-destructive"
                  onClick={() => deleteCustomer(c.username)}
                >
                  Delete
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function Analytics() {
  const { data } = useQuery<AdminAnalytics>({
    queryKey: ["admin-analytics"],
    queryFn: () => apiFetch("/api/admin/analytics"),
  });

  if (!data) return null;

  return (
    <div className="space-y-3">
      <h3 className="text-base font-semibold">Analytics</h3>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <MetricCard label="Active (7d)" value={data.active_users_7d} />
        <MetricCard label="Active (30d)" value={data.active_users_30d} />
        <MetricCard
          label="Brand Watchlist Users"
          value={data.adoption.brand_watchlist_users}
        />
        <MetricCard
          label="Feedback Users"
          value={data.adoption.alert_feedback_users}
        />
      </div>
    </div>
  );
}

function PipelineHealth() {
  const { data } = usePipelineHealth();

  if (!data) return null;

  return (
    <div className="space-y-3">
      <h3 className="text-base font-semibold">Pipeline Health</h3>
      <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
        {Object.entries(data.pipelines).map(([name, info]) => (
          <Card key={name}>
            <CardContent className="p-3">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium">{name}</p>
                <Badge
                  variant={info.status === "healthy" ? "secondary" : "destructive"}
                  className="text-[10px]"
                >
                  {info.status}
                </Badge>
              </div>
              <div className="mt-1 flex gap-3 text-xs text-muted-foreground">
                <span>{info.row_count.toLocaleString()} rows</span>
                <span>{info.age_hours.toFixed(1)}h ago</span>
              </div>
              {info.error_preview && (
                <p className="mt-1 text-xs text-destructive">
                  {info.error_preview}
                </p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

export default function AdminPage() {
  const { isAdmin, isLoading } = useAuth();

  if (isLoading) return null;
  if (!isAdmin) {
    redirect("/");
  }

  return (
    <DashboardShell>
      <div className="mx-auto max-w-5xl space-y-8">
        <h2 className="text-xl font-bold">Admin Panel</h2>
        <Customers />
        <Analytics />
        <PipelineHealth />
      </div>
    </DashboardShell>
  );
}
