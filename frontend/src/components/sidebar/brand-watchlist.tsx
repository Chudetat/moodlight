"use client";

import { useState } from "react";
import { useAuth } from "@/lib/hooks/use-auth";
import {
  useBrands,
  useAddBrand,
  useRemoveBrand,
  useUserTeam,
  useTeamWatchlists,
} from "@/lib/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useDashboardStore } from "@/store/dashboard-store";

export function BrandWatchlist() {
  const { username } = useAuth();
  const { data } = useBrands(username);
  const { data: teamData } = useUserTeam();
  const team = teamData?.team;
  const { data: teamWatchlists } = useTeamWatchlists(team?.id);
  const addBrand = useAddBrand();
  const removeBrand = useRemoveBrand();
  const [newBrand, setNewBrand] = useState("");
  const setFocusedBrand = useDashboardStore((s) => s.setFocusedBrand);
  const focusedBrand = useDashboardStore((s) => s.focusedBrand);

  const brands = data?.brands ?? [];
  const sharedBrands = new Set(teamWatchlists?.brands ?? []);
  const isOwner = team?.role === "owner";

  const handleAdd = () => {
    const name = newBrand.trim();
    if (!name) return;
    addBrand.mutate(name, {
      onSuccess: () => setNewBrand(""),
    });
  };

  return (
    <div className="space-y-2">
      <p className="text-xs font-medium uppercase text-muted-foreground">
        Brand Watchlist ({brands.length}/5)
      </p>
      {brands.length === 0 && (
        <p className="text-xs text-muted-foreground">
          Add your first brand to unlock VLDS tracking.
        </p>
      )}
      {brands.map((b) => {
        const isShared = sharedBrands.has(b) && !isOwner;
        return (
          <div key={b} className="flex items-center justify-between">
            <div className="flex items-center gap-1">
              <button
                className={`text-sm font-medium ${
                  focusedBrand === b ? "text-primary" : ""
                }`}
                onClick={() =>
                  setFocusedBrand(focusedBrand === b ? null : b)
                }
              >
                {b}
              </button>
              {isShared && (
                <Badge
                  variant="outline"
                  className="px-1 py-0 text-[10px]"
                >
                  shared
                </Badge>
              )}
            </div>
            {!isShared && (
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-2 text-xs text-muted-foreground hover:text-destructive"
                onClick={() => {
                  if (focusedBrand === b) setFocusedBrand(null);
                  removeBrand.mutate(b);
                }}
                disabled={removeBrand.isPending}
              >
                Remove
              </Button>
            )}
          </div>
        );
      })}
      {brands.length < 5 && (
        <div className="flex gap-1">
          <Input
            placeholder="e.g. Nike"
            value={newBrand}
            onChange={(e) => setNewBrand(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            className="h-8 text-sm"
          />
          <Button
            size="sm"
            className="h-8"
            onClick={handleAdd}
            disabled={addBrand.isPending}
          >
            Add
          </Button>
        </div>
      )}
      {addBrand.isError && (
        <p className="text-xs text-destructive">
          {(addBrand.error as Error).message}
        </p>
      )}
    </div>
  );
}
