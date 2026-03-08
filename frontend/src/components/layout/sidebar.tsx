"use client";

import Image from "next/image";
import Link from "next/link";
import { useAuth } from "@/lib/hooks/use-auth";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { LogOut } from "lucide-react";
import { BrandWatchlist } from "@/components/sidebar/brand-watchlist";
import { TopicWatchlist } from "@/components/sidebar/topic-watchlist";
import { EmailPreferences } from "@/components/sidebar/email-preferences";
import { ReportGenerator } from "@/components/sidebar/report-generator";
import { BriefGenerator } from "@/components/sidebar/brief-generator";

const STRIPE_PORTAL_LINK = process.env.NEXT_PUBLIC_STRIPE_PORTAL_LINK;

export function Sidebar() {
  const { session, logout, isLoading } = useAuth();

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
