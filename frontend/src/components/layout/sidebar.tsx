"use client";

import Image from "next/image";
import Link from "next/link";
import { useAuth } from "@/lib/hooks/use-auth";
import { useDashboardStore } from "@/store/dashboard-store";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { LogOut } from "lucide-react";
import { BrandWatchlist } from "@/components/sidebar/brand-watchlist";
import { TopicWatchlist } from "@/components/sidebar/topic-watchlist";
import { GettingStarted } from "@/components/sidebar/getting-started";
import { NotificationBell } from "@/components/sidebar/notification-bell";
import { EmailPreferences } from "@/components/sidebar/email-preferences";
import { ReportGenerator } from "@/components/sidebar/report-generator";
import { ScheduledReports } from "@/components/sidebar/scheduled-reports";
import { BriefGenerator } from "@/components/sidebar/brief-generator";
import { AlertSettings } from "@/components/sidebar/alert-settings";
import { TeamSection } from "@/components/sidebar/team-section";
import { ContactSupport } from "@/components/sidebar/contact-support";

const STRIPE_PORTAL_LINK = process.env.NEXT_PUBLIC_STRIPE_PORTAL_LINK;

export function Sidebar() {
  const { session, logout, isLoading } = useAuth();
  const searchQuery = useDashboardStore((s) => s.searchQuery);
  const setSearchQuery = useDashboardStore((s) => s.setSearchQuery);
  const compareMode = useDashboardStore((s) => s.compareMode);
  const setCompareMode = useDashboardStore((s) => s.setCompareMode);
  const compareBrands = useDashboardStore((s) => s.compareBrands);
  const setCompareBrands = useDashboardStore((s) => s.setCompareBrands);
  const days = useDashboardStore((s) => s.days);
  const setDays = useDashboardStore((s) => s.setDays);

  return (
    <aside className="flex h-screen w-72 flex-col border-r border-border bg-card">
      {/* Logo */}
      <div className="flex items-center px-4 py-4">
        <Image
          src="/logo.png"
          alt="Moodlight"
          width={140}
          height={28}
          className="h-7 w-auto"
          priority
        />
      </div>

      <Separator />

      <ScrollArea className="flex-1 px-4 py-4">
        {/* User info */}
        {isLoading ? (
          <div className="space-y-2">
            <div className="h-4 w-24 animate-pulse rounded bg-muted" />
            <div className="h-3 w-32 animate-pulse rounded bg-muted" />
          </div>
        ) : session ? (
          <div className="space-y-1">
            <p className="text-sm font-medium">{session.username}</p>
            <p className="text-xs text-muted-foreground">{session.email}</p>
            <Badge variant="secondary" className="mt-1 text-xs capitalize">
              {session.tier}
            </Badge>
          </div>
        ) : null}

        <Separator className="my-4" />

        {/* Controls */}
        <p className="mb-2 text-xs font-medium uppercase text-muted-foreground">
          Controls
        </p>
        <div className="space-y-3">
          <Input
            placeholder='Search for a topic, e.g. "student loans"'
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-8 text-sm"
          />
          <div className="flex items-center justify-between">
            <Label htmlFor="compare-mode" className="text-sm">
              Compare Brands
            </Label>
            <Switch
              id="compare-mode"
              checked={compareMode}
              onCheckedChange={setCompareMode}
            />
          </div>
          {compareMode && (
            <div className="space-y-2 pl-1">
              {[0, 1, 2].map((i) => (
                <Input
                  key={i}
                  placeholder={
                    i < 2 ? `Brand ${i + 1}` : "Brand 3 (optional)"
                  }
                  value={compareBrands[i] ?? ""}
                  onChange={(e) => {
                    const next = [...compareBrands];
                    next[i] = e.target.value;
                    setCompareBrands(next);
                  }}
                  className="h-7 text-xs"
                />
              ))}
            </div>
          )}
          <div className="space-y-1">
            <Label className="text-sm">Time Range</Label>
            <Select
              value={String(days)}
              onValueChange={(v) => v && setDays(Number(v))}
            >
              <SelectTrigger className="h-8 text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[7, 30, 60, 90].map((d) => (
                  <SelectItem key={d} value={String(d)}>
                    Last {d} days
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <Separator className="my-4" />

        {/* Watchlists */}
        <BrandWatchlist />
        <Separator className="my-3" />
        <TopicWatchlist />
        <Separator className="my-3" />

        {/* Getting Started */}
        <GettingStarted />
        <Separator className="my-3" />

        {/* Notification Bell */}
        <NotificationBell />
        <Separator className="my-3" />

        {/* Report generator */}
        <ReportGenerator />
        <Separator className="my-3" />

        {/* Scheduled Reports */}
        <ScheduledReports />
        <Separator className="my-3" />

        {/* Brief generator */}
        <BriefGenerator />
        <Separator className="my-3" />

        {/* Email preferences */}
        <EmailPreferences />
        <Separator className="my-3" />

        {/* Alert settings */}
        <AlertSettings />
        <Separator className="my-3" />

        {/* Team */}
        <TeamSection />
        <Separator className="my-3" />

        {/* Contact Support */}
        <ContactSupport />
      </ScrollArea>

      {/* Footer */}
      <div className="space-y-1 border-t border-border p-4">
        {STRIPE_PORTAL_LINK && (
          <a
            href={STRIPE_PORTAL_LINK}
            target="_blank"
            rel="noopener noreferrer"
            className="block text-xs text-muted-foreground hover:text-foreground"
          >
            Manage subscription
          </a>
        )}
        {session?.is_admin && (
          <Link
            href="/admin"
            className="block text-xs text-muted-foreground hover:text-foreground"
          >
            Admin Panel
          </Link>
        )}
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start text-muted-foreground"
          onClick={logout}
        >
          <LogOut className="mr-2 h-4 w-4" />
          Log out
        </Button>
      </div>
    </aside>
  );
}
