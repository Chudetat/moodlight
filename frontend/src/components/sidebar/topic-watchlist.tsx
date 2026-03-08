"use client";

import { useState } from "react";
import { useAuth } from "@/lib/hooks/use-auth";
import { useTopics, useAddTopic, useRemoveTopic } from "@/lib/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { TOPIC_CATEGORIES } from "@/lib/constants";

export function TopicWatchlist() {
  const { username } = useAuth();
  const { data } = useTopics(username);
  const addTopic = useAddTopic();
  const removeTopic = useRemoveTopic();
  const [mode, setMode] = useState<"category" | "custom">("category");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [customTopic, setCustomTopic] = useState("");

  const topics = data?.topics ?? [];

  const handleAdd = () => {
    if (mode === "category" && selectedCategory) {
      addTopic.mutate(
        { topic_name: selectedCategory, is_category: true },
        { onSuccess: () => setSelectedCategory("") }
      );
    } else if (mode === "custom" && customTopic.trim()) {
      addTopic.mutate(
        { topic_name: customTopic.trim(), is_category: false },
        { onSuccess: () => setCustomTopic("") }
      );
    }
  };

  return (
    <div className="space-y-2">
      <p className="text-xs font-medium uppercase text-muted-foreground">
        Topic Watchlist ({topics.length}/10)
      </p>
      {topics.length === 0 && (
        <p className="text-xs text-muted-foreground">
          Add a topic to monitor sentiment shifts.
        </p>
      )}
      {topics.map((t) => (
        <div
          key={t.topic_name}
          className="flex items-center justify-between"
        >
          <div className="flex items-center gap-1">
            <span className="text-sm font-medium">{t.topic_name}</span>
            {t.is_category && (
              <Badge variant="outline" className="px-1 py-0 text-[10px]">
                cat
              </Badge>
            )}
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-xs text-muted-foreground hover:text-destructive"
            onClick={() => removeTopic.mutate(t.topic_name)}
            disabled={removeTopic.isPending}
          >
            Remove
          </Button>
        </div>
      ))}
      {topics.length < 10 && (
        <div className="space-y-2">
          <div className="flex gap-2 text-xs">
            <button
              className={`${
                mode === "category"
                  ? "font-medium text-foreground"
                  : "text-muted-foreground"
              }`}
              onClick={() => setMode("category")}
            >
              Category
            </button>
            <button
              className={`${
                mode === "custom"
                  ? "font-medium text-foreground"
                  : "text-muted-foreground"
              }`}
              onClick={() => setMode("custom")}
            >
              Custom
            </button>
          </div>
          {mode === "category" ? (
            <div className="flex gap-1">
              <Select
                value={selectedCategory}
                onValueChange={(v) => setSelectedCategory(v ?? "")}
              >
                <SelectTrigger className="h-8 text-sm">
                  <SelectValue placeholder="Select category" />
                </SelectTrigger>
                <SelectContent>
                  {TOPIC_CATEGORIES.map((c) => (
                    <SelectItem key={c} value={c}>
                      {c}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                size="sm"
                className="h-8"
                onClick={handleAdd}
                disabled={addTopic.isPending}
              >
                Add
              </Button>
            </div>
          ) : (
            <div className="flex gap-1">
              <Input
                placeholder="e.g. student loans"
                value={customTopic}
                onChange={(e) => setCustomTopic(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAdd()}
                className="h-8 text-sm"
              />
              <Button
                size="sm"
                className="h-8"
                onClick={handleAdd}
                disabled={addTopic.isPending}
              >
                Add
              </Button>
            </div>
          )}
        </div>
      )}
      {addTopic.isError && (
        <p className="text-xs text-destructive">
          {(addTopic.error as Error).message}
        </p>
      )}
    </div>
  );
}
