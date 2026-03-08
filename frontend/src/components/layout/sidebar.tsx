"use client";

import { useAuth } from "@/lib/hooks/use-auth";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { LogOut, BarChart3 } from "lucide-react";
import { BrandWatchlist } from "@/components/sidebar/brand-watchlist";
import { TopicWatchlist } from "@/components/sidebar/topic-watchlist";
import { EmailPreferences } from "@/components/sidebar/email-preferences";
import { ReportGenerator } from "@/components/sidebar/report-generator";
import { BriefGenerator } from "@/components/sidebar/brief-generator";

export function Sidebar() {
  const { session, logout, isLoading } = useAuth();

  return (
    <aside className="flex h-screen w-64 flex-col border-r border-border bg-card">
      {/* Logo */}
      <div className="flex items-center gap-2 px-4 py-5">
        <BarChart3 className="h-6 w-6 text-primary" />
        <span className="text-lg font-bold tracking-tight">Moodlight</span>
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

        {/* Watchlists */}
        <BrandWatchlist />
        <Separator className="my-3" />
        <TopicWatchlist />
        <Separator className="my-3" />

        {/* Email preferences */}
        <EmailPreferences />
        <Separator className="my-3" />

        {/* Report generator */}
        <ReportGenerator />
        <Separator className="my-3" />

        {/* Brief generator */}
        <BriefGenerator />
      </ScrollArea>

      {/* Logout */}
      <div className="border-t border-border p-4">
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
