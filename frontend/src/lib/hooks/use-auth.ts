"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useCallback } from "react";
import type { SessionResponse } from "../types";

export function useAuth() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const {
    data: session,
    isLoading,
    error,
  } = useQuery<SessionResponse>({
    queryKey: ["session"],
    queryFn: async () => {
      const res = await fetch("/api/auth/session");
      if (!res.ok) throw new Error("Not authenticated");
      return res.json();
    },
    retry: false,
    staleTime: 5 * 60 * 1000, // 5 min
  });

  const logout = useCallback(async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    queryClient.clear();
    router.push("/login");
  }, [queryClient, router]);

  return {
    session,
    isLoading,
    isAuthenticated: !!session,
    isAdmin: session?.is_admin ?? false,
    tier: session?.tier ?? "free",
    username: session?.username ?? "",
    briefCredits: session?.brief_credits ?? 0,
    error,
    logout,
  };
}
