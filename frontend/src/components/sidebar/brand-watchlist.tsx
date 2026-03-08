"use client";

import { useState } from "react";
import { useAuth } from "@/lib/hooks/use-auth";
import { useBrands } from "@/lib/hooks/use-api";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { X, Plus } from "lucide-react";
import { TIER_LIMITS } from "@/lib/constants";
import { useDashboardStore } from "@/store/dashboard-store";

export function BrandWatchlist() {
  const { username } = useAuth();
  const { data } = useBrands(username);
  const queryClient = useQueryClient();
  const [newBrand, setNewBrand] = useState("");
  const [loading, setLoading] = useState(false);
  const setFocusedBrand = useDashboardStore((s) => s.setFocusedBrand);
  const focusedBrand = useDashboardStore((s) => s.focusedBrand);

  const brands = data?.brands ?? [];
  const atLimit = brands.length >= TIER_LIMITS.brand_watchlist_max;

  async function addBrand(e: React.FormEvent) {
    e.preventDefault();
    if (!newBrand.trim() || atLimit) return;
    setLoading(true);
    try {
      await fetch("/api/proxy/api/watchlist/brands", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ brand_name: newBrand.trim() }),
      });
      setNewBrand("");
      queryClient.invalidateQueries({ queryKey: ["brands"] });
    } finally {
      setLoading(false);
    }
  }

  async function removeBrand(brand: string) {
    await fetch(`/api/proxy/api/watchlist/brands/${encodeURIComponent(brand)}`, {
      method: "DELETE",
    });
    if (focusedBrand === brand) setFocusedBrand(null);
    queryClient.invalidateQueries({ queryKey: ["brands"] });
  }

  return (
    <div className="space-y-2">
      <p className="text-xs font-medium text-muted-foreground">
        Brand Watchlist ({brands.length}/{TIER_LIMITS.brand_watchlist_max})
      </p>
      <div className="flex flex-wrap gap-1.5">
        {brands.map((b) => (
          <Badge
            key={b}
            variant={focusedBrand === b ? "default" : "secondary"}
            className="cursor-pointer gap-1 text-xs"
            onClick={() =>
              setFocusedBrand(focusedBrand === b ? null : b)
            }
          >
            {b}
            <button
              onClick={(e) => {
                e.stopPropagation();
                removeBrand(b);
              }}
              className="ml-0.5 hover:text-destructive"
            >
              <X className="h-2.5 w-2.5" />
            </button>
          </Badge>
        ))}
      </div>
      {!atLimit && (
        <form onSubmit={addBrand} className="flex gap-1.5">
          <Input
            value={newBrand}
            onChange={(e) => setNewBrand(e.target.value)}
            placeholder="Add brand..."
            className="h-7 text-xs"
          />
          <Button type="submit" size="icon-xs" disabled={loading || !newBrand.trim()}>
            <Plus className="h-3 w-3" />
          </Button>
        </form>
      )}
    </div>
  );
}
