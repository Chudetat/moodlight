"use client";

import { useState } from "react";
import { useAuth } from "@/lib/hooks/use-auth";
import { useTopics } from "@/lib/hooks/use-api";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { X, Plus } from "lucide-react";
import { TIER_LIMITS } from "@/lib/constants";

export function TopicWatchlist() {
  const { username } = useAuth();
  const { data } = useTopics(username);
  const queryClient = useQueryClient();
  const [newTopic, setNewTopic] = useState("");
  const [loading, setLoading] = useState(false);

  const topics = data?.topics ?? [];
  const atLimit = topics.length >= TIER_LIMITS.topic_watchlist_max;

  async function addTopic(e: React.FormEvent) {
    e.preventDefault();
    if (!newTopic.trim() || atLimit) return;
    setLoading(true);
    try {
      await fetch("/api/proxy/api/watchlist/topics", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic_name: newTopic.trim() }),
      });
      setNewTopic("");
      queryClient.invalidateQueries({ queryKey: ["topics"] });
    } finally {
      setLoading(false);
    }
  }

  async function removeTopic(topic: string) {
    await fetch(`/api/proxy/api/watchlist/topics/${encodeURIComponent(topic)}`, {
      method: "DELETE",
    });
    queryClient.invalidateQueries({ queryKey: ["topics"] });
  }

  return (
    <div className="space-y-2">
      <p className="text-xs font-medium text-muted-foreground">
        Topic Watchlist ({topics.length}/{TIER_LIMITS.topic_watchlist_max})
      </p>
      <div className="flex flex-wrap gap-1.5">
        {topics.map((t) => (
          <Badge key={t.topic_name} variant="secondary" className="gap-1 text-xs">
            {t.topic_name}
            {t.is_category && (
              <span className="text-[9px] text-muted-foreground">(cat)</span>
            )}
            <button
              onClick={() => removeTopic(t.topic_name)}
              className="ml-0.5 hover:text-destructive"
            >
              <X className="h-2.5 w-2.5" />
            </button>
          </Badge>
        ))}
      </div>
      {!atLimit && (
        <form onSubmit={addTopic} className="flex gap-1.5">
          <Input
            value={newTopic}
            onChange={(e) => setNewTopic(e.target.value)}
            placeholder="Add topic..."
            className="h-7 text-xs"
          />
          <Button type="submit" size="icon-xs" disabled={loading || !newTopic.trim()}>
            <Plus className="h-3 w-3" />
          </Button>
        </form>
      )}
    </div>
  );
}
