"use client";

import { useAuth } from "@/lib/hooks/use-auth";

export function Header() {
  const { session } = useAuth();

  return (
    <header className="flex h-14 items-center border-b border-border px-6">
      <h1 className="text-lg font-semibold">
        Intelligence Dashboard
      </h1>
      {session?.is_admin && (
        <span className="ml-2 rounded bg-primary/20 px-2 py-0.5 text-xs font-medium text-primary">
          Admin
        </span>
      )}
    </header>
  );
}
