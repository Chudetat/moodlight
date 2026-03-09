"use client";

import { useState } from "react";
import { useAuth } from "@/lib/hooks/use-auth";
import {
  usePipelineHealth,
  useAdminCustomers,
  useCreateCustomer,
  useUpdateCustomer,
  useDeleteCustomer,
  useAddCredits,
  useAdminTeams,
  useCreateUserTeam,
} from "@/lib/hooks/use-api";
import { DashboardShell } from "@/components/layout/dashboard-shell";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { MetricCard } from "@/components/charts/metric-card";
import { redirect } from "next/navigation";
import type { AdminAnalytics, AskQueriesResponse } from "@/lib/types";

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`/api/proxy${path}`);
  if (!res.ok) throw new Error("Failed to fetch");
  return res.json();
}

// ── Customers List ──────────────────────────────────

function Customers() {
  const { data } = useAdminCustomers();
  const deleteMutation = useDeleteCustomer();
  const [search, setSearch] = useState("");

  const customers = (data?.customers ?? []).filter(
    (c) =>
      c.email.toLowerCase().includes(search.toLowerCase()) ||
      c.username.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-3">
      <h3 className="text-base font-semibold">
        Customers ({data?.customers?.length ?? 0})
      </h3>
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
                  {c.extra_seats} seat{c.extra_seats !== 1 ? "s" : ""}
                </span>
                <span className="text-xs text-muted-foreground">
                  {c.brief_credits} credits
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 text-xs text-destructive"
                  onClick={() => {
                    if (confirm(`Delete customer ${c.username}?`)) {
                      deleteMutation.mutate(c.username);
                    }
                  }}
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

// ── Create Customer ─────────────────────────────────

function CreateCustomer() {
  const createMutation = useCreateCustomer();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [tier, setTier] = useState("monthly");
  const [result, setResult] = useState<{
    username: string;
    temp_password: string;
  } | null>(null);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name || !email) return;
    try {
      const data = await createMutation.mutateAsync({ name, email, tier });
      setResult({ username: data.username, temp_password: data.temp_password });
      setName("");
      setEmail("");
    } catch {
      // error shown via mutation state
    }
  }

  return (
    <div className="space-y-3">
      <h3 className="text-base font-semibold">Add Customer</h3>
      <form onSubmit={handleCreate} className="space-y-3">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <div className="space-y-1">
            <Label className="text-xs">Name</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Full name"
              className="h-8 text-xs"
              required
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Email</Label>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="email@example.com"
              className="h-8 text-xs"
              required
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Tier</Label>
            <Select value={tier} onValueChange={(v) => v && setTier(v)}>
              <SelectTrigger className="h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="monthly">Monthly</SelectItem>
                <SelectItem value="annually">Annual</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <Button
          type="submit"
          size="sm"
          disabled={createMutation.isPending}
          className="text-xs"
        >
          {createMutation.isPending ? "Creating..." : "Create Customer"}
        </Button>
        {createMutation.isError && (
          <p className="text-xs text-destructive">
            {createMutation.error?.message || "Failed to create customer."}
          </p>
        )}
      </form>
      {result && (
        <Card className="border-green-500/30 bg-green-500/5">
          <CardContent className="p-3">
            <p className="text-sm font-medium text-green-400">
              Customer created
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Username: <span className="font-mono text-foreground">{result.username}</span>
            </p>
            <p className="text-xs text-muted-foreground">
              Temp password: <span className="font-mono text-foreground">{result.temp_password}</span>
            </p>
            <p className="mt-1 text-[10px] text-muted-foreground">
              Share these credentials with the customer.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ── Edit Customer ───────────────────────────────────

function EditCustomer() {
  const { data } = useAdminCustomers();
  const updateMutation = useUpdateCustomer();
  const [selectedUsername, setSelectedUsername] = useState("");
  const [tier, setTier] = useState("");
  const [extraSeats, setExtraSeats] = useState("");
  const [success, setSuccess] = useState(false);

  const customers = data?.customers ?? [];
  const selected = customers.find((c) => c.username === selectedUsername);

  function handleSelect(username: string) {
    setSelectedUsername(username);
    const c = customers.find((cu) => cu.username === username);
    if (c) {
      setTier(c.tier);
      setExtraSeats(String(c.extra_seats));
    }
    setSuccess(false);
  }

  async function handleUpdate(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedUsername) return;
    try {
      await updateMutation.mutateAsync({
        username: selectedUsername,
        tier,
        extra_seats: Number(extraSeats) || 0,
      });
      setSuccess(true);
    } catch {
      // error shown via mutation state
    }
  }

  return (
    <div className="space-y-3">
      <h3 className="text-base font-semibold">Edit Customer</h3>
      <div className="space-y-1">
        <Label className="text-xs">Select Customer</Label>
        <Select value={selectedUsername} onValueChange={(v) => v && handleSelect(v)}>
          <SelectTrigger className="h-8 text-xs">
            <SelectValue placeholder="Choose a customer..." />
          </SelectTrigger>
          <SelectContent>
            {customers.map((c) => (
              <SelectItem key={c.username} value={c.username}>
                {c.username} ({c.email})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {selected && (
        <form onSubmit={handleUpdate} className="space-y-3">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div className="space-y-1">
              <Label className="text-xs">Tier</Label>
              <Select value={tier} onValueChange={(v) => v && setTier(v)}>
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="monthly">Monthly</SelectItem>
                  <SelectItem value="annually">Annual</SelectItem>
                  <SelectItem value="professional">Professional</SelectItem>
                  <SelectItem value="enterprise">Enterprise</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Extra Seats</Label>
              <Input
                type="number"
                value={extraSeats}
                onChange={(e) => setExtraSeats(e.target.value)}
                className="h-8 text-xs"
                min={0}
              />
            </div>
          </div>
          <Button
            type="submit"
            size="sm"
            disabled={updateMutation.isPending}
            className="text-xs"
          >
            {updateMutation.isPending ? "Saving..." : "Save Changes"}
          </Button>
          {updateMutation.isError && (
            <p className="text-xs text-destructive">
              {updateMutation.error?.message || "Update failed."}
            </p>
          )}
          {success && (
            <p className="text-xs text-green-400">Updated successfully.</p>
          )}
        </form>
      )}
    </div>
  );
}

// ── Add Credits ─────────────────────────────────────

function AddCredits() {
  const { data } = useAdminCustomers();
  const creditsMutation = useAddCredits();
  const [selectedUsername, setSelectedUsername] = useState("");
  const [credits, setCredits] = useState("10");
  const [success, setSuccess] = useState(false);

  const customers = data?.customers ?? [];

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedUsername || !credits) return;
    setSuccess(false);
    try {
      await creditsMutation.mutateAsync({
        username: selectedUsername,
        credits: Number(credits),
      });
      setSuccess(true);
    } catch {
      // error shown via mutation state
    }
  }

  return (
    <div className="space-y-3">
      <h3 className="text-base font-semibold">Add Credits</h3>
      <form onSubmit={handleAdd} className="space-y-3">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <div className="space-y-1">
            <Label className="text-xs">Customer</Label>
            <Select
              value={selectedUsername}
              onValueChange={(v) => {
                if (!v) return;
                setSelectedUsername(v);
                setSuccess(false);
              }}
            >
              <SelectTrigger className="h-8 text-xs">
                <SelectValue placeholder="Choose a customer..." />
              </SelectTrigger>
              <SelectContent>
                {customers.map((c) => (
                  <SelectItem key={c.username} value={c.username}>
                    {c.username} — {c.brief_credits} credits
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Credits to Add</Label>
            <Input
              type="number"
              value={credits}
              onChange={(e) => setCredits(e.target.value)}
              className="h-8 text-xs"
              min={1}
            />
          </div>
        </div>
        <Button
          type="submit"
          size="sm"
          disabled={creditsMutation.isPending}
          className="text-xs"
        >
          {creditsMutation.isPending ? "Adding..." : "Add Credits"}
        </Button>
        {creditsMutation.isError && (
          <p className="text-xs text-destructive">
            {creditsMutation.error?.message || "Failed to add credits."}
          </p>
        )}
        {success && (
          <p className="text-xs text-green-400">
            Added {credits} credits to {selectedUsername}.
          </p>
        )}
      </form>
    </div>
  );
}

// ── Teams ───────────────────────────────────────────

function Teams() {
  const { data } = useAdminTeams();
  const { data: customersData } = useAdminCustomers();
  const createTeamMutation = useCreateUserTeam();
  const [teamName, setTeamName] = useState("");
  const [ownerUsername, setOwnerUsername] = useState("");
  const [success, setSuccess] = useState(false);

  const teams = (data?.teams ?? []) as Array<{
    id: number;
    team_name: string;
    owner_username: string;
    member_count: number;
  }>;
  const customers = customersData?.customers ?? [];

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!teamName || !ownerUsername) return;
    setSuccess(false);
    try {
      await createTeamMutation.mutateAsync({
        team_name: teamName,
        owner_username: ownerUsername,
      });
      setTeamName("");
      setSuccess(true);
    } catch {
      // error shown via mutation state
    }
  }

  return (
    <div className="space-y-3">
      <h3 className="text-base font-semibold">Teams ({teams.length})</h3>

      {teams.length > 0 && (
        <div className="space-y-2">
          {teams.map((t) => (
            <Card key={t.id}>
              <CardContent className="flex items-center justify-between p-3">
                <div>
                  <p className="text-sm font-medium">{t.team_name}</p>
                  <p className="text-xs text-muted-foreground">
                    Owner: {t.owner_username}
                  </p>
                </div>
                <Badge variant="secondary" className="text-[10px]">
                  {t.member_count} member{t.member_count !== 1 ? "s" : ""}
                </Badge>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <form onSubmit={handleCreate} className="space-y-3">
        <p className="text-xs font-medium text-muted-foreground">
          Create New Team
        </p>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <div className="space-y-1">
            <Label className="text-xs">Team Name</Label>
            <Input
              value={teamName}
              onChange={(e) => setTeamName(e.target.value)}
              placeholder="e.g. Marketing"
              className="h-8 text-xs"
              required
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Owner</Label>
            <Select value={ownerUsername} onValueChange={(v) => v && setOwnerUsername(v)}>
              <SelectTrigger className="h-8 text-xs">
                <SelectValue placeholder="Select owner..." />
              </SelectTrigger>
              <SelectContent>
                {customers.map((c) => (
                  <SelectItem key={c.username} value={c.username}>
                    {c.username}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <Button
          type="submit"
          size="sm"
          disabled={createTeamMutation.isPending}
          className="text-xs"
        >
          {createTeamMutation.isPending ? "Creating..." : "Create Team"}
        </Button>
        {createTeamMutation.isError && (
          <p className="text-xs text-destructive">
            {createTeamMutation.error?.message || "Failed to create team."}
          </p>
        )}
        {success && (
          <p className="text-xs text-green-400">Team created.</p>
        )}
      </form>
    </div>
  );
}

// ── Analytics ───────────────────────────────────────

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

// ── Ask Queries ─────────────────────────────────────

function AskQueries() {
  const { data } = useQuery<AskQueriesResponse>({
    queryKey: ["admin-ask-queries"],
    queryFn: () => apiFetch("/api/admin/ask-queries"),
  });

  if (!data) return null;

  return (
    <div className="space-y-3">
      <h3 className="text-base font-semibold">Ask Moodlight Widget</h3>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <MetricCard label="Total Queries" value={data.total} />
        <MetricCard label="Free" value={data.free} />
        <MetricCard label="Paid" value={data.paid} />
        <MetricCard label="Unique Visitors" value={data.unique_visitors} />
      </div>

      {data.top_brands.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-medium text-muted-foreground">
            Top Brands Asked About
          </p>
          <div className="flex flex-wrap gap-1.5">
            {data.top_brands.map((brand) => (
              <Badge key={brand} variant="secondary" className="text-[10px]">
                {brand}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {data.queries.length > 0 && (
        <div className="max-h-80 overflow-x-auto overflow-y-auto rounded-lg border border-border">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-card">
              <tr className="border-b border-border text-left">
                <th className="p-2 font-medium text-muted-foreground">Time</th>
                <th className="p-2 font-medium text-muted-foreground">Question</th>
                <th className="p-2 font-medium text-muted-foreground">Brand</th>
                <th className="p-2 font-medium text-muted-foreground">Topic</th>
                <th className="p-2 font-medium text-muted-foreground">Paid</th>
              </tr>
            </thead>
            <tbody>
              {data.queries.map((q) => (
                <tr key={q.id} className="border-b border-border/50">
                  <td className="whitespace-nowrap p-2 text-muted-foreground">
                    {new Date(q.created_at).toLocaleDateString("en-US", {
                      month: "short",
                      day: "numeric",
                    })}{" "}
                    {new Date(q.created_at).toLocaleTimeString("en-US", {
                      hour: "numeric",
                      minute: "2-digit",
                    })}
                  </td>
                  <td className="max-w-xs truncate p-2">{q.question}</td>
                  <td className="p-2 text-muted-foreground">
                    {q.detected_brand || "\u2014"}
                  </td>
                  <td className="p-2 text-muted-foreground">
                    {q.detected_topic || "\u2014"}
                  </td>
                  <td className="p-2">
                    {q.is_paid ? (
                      <span className="text-green-400">Yes</span>
                    ) : (
                      <span className="text-muted-foreground">No</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Pipeline Health ─────────────────────────────────

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
                <span>{(info.age_hours ?? 0).toFixed(1)}h ago</span>
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

// ── Main ────────────────────────────────────────────

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
        <CreateCustomer />
        <EditCustomer />
        <AddCredits />
        <Teams />
        <Analytics />
        <AskQueries />
        <PipelineHealth />
      </div>
    </DashboardShell>
  );
}
