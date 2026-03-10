"use client";

import { useMemo, useState, useCallback } from "react";
import { useCombinedData } from "@/lib/hooks/use-api";
import { cleanSourceName } from "@/lib/utils";
import { Button } from "@/components/ui/button";

function empathyLabel(raw: number): string {
  if (raw < 0.04) return "Cold / Hostile";
  if (raw < 0.10) return "Detached / Neutral";
  if (raw < 0.30) return "Warm / Supportive";
  return "Highly Empathetic";
}

type SortKey = "created_at" | "empathy_score" | "engagement" | "topic" | "source";

interface RowData {
  text: string;
  source: string;
  topic: string;
  empathy_label: string;
  empathy_score: number;
  emotion: string;
  engagement: number;
  created_at: string;
  created_display: string;
}

export function WorldViewTable() {
  const { data, isLoading } = useCombinedData(7);
  const [sortBy, setSortBy] = useState<SortKey>("created_at");
  const [sortAsc, setSortAsc] = useState(false);

  const rows = useMemo<RowData[]>(() => {
    const raw = data?.data ?? [];
    if (raw.length === 0) return [];

    const now = Date.now();
    const seventyTwoHoursMs = 72 * 60 * 60 * 1000;

    return raw
      .filter((r) => {
        const createdAt = new Date(String(r.created_at ?? "")).getTime();
        return !isNaN(createdAt) && now - createdAt < seventyTwoHoursMs;
      })
      .map((r) => ({
        text: String(r.text ?? "").slice(0, 200),
        source: cleanSourceName(String(r.source ?? "unknown")),
        topic: String(r.topic ?? ""),
        empathy_label: empathyLabel(Number(r.empathy_score ?? 0)),
        empathy_score: Number(r.empathy_score ?? 0),
        emotion: String(r.emotion_top_1 ?? ""),
        engagement: Number(r.engagement ?? 0),
        created_at: String(r.created_at ?? ""),
        created_display: (() => {
          const d = new Date(String(r.created_at ?? ""));
          const mo = d.getMonth() + 1;
          const day = d.getDate();
          const hour = d.getHours();
          const min = d.getMinutes().toString().padStart(2, "0");
          const h12 = hour % 12 || 12;
          const ap = hour >= 12 ? "p" : "a";
          return `${mo}/${day} ${h12}:${min}${ap}`;
        })(),
      }))
      .sort((a, b) => {
        const av = a[sortBy];
        const bv = b[sortBy];
        if (typeof av === "number" && typeof bv === "number") {
          return sortAsc ? av - bv : bv - av;
        }
        return sortAsc
          ? String(av).localeCompare(String(bv))
          : String(bv).localeCompare(String(av));
      })
      .slice(0, 3000);
  }, [data, sortBy, sortAsc]);

  const handleSort = useCallback(
    (key: SortKey) => {
      if (sortBy === key) {
        setSortAsc(!sortAsc);
      } else {
        setSortBy(key);
        setSortAsc(false);
      }
    },
    [sortBy, sortAsc]
  );

  const handleExport = useCallback(() => {
    if (rows.length === 0) return;
    const headers = [
      "Post",
      "Source",
      "Topic",
      "Empathy",
      "Emotion",
      "Engagement",
      "Posted",
    ];
    const csvRows = rows.map((r) =>
      [
        r.text,
        r.source,
        r.topic,
        r.empathy_label,
        r.emotion,
        r.engagement,
        r.created_at,
      ]
        .map((v) => `"${String(v).replace(/"/g, '""')}"`)
        .join(",")
    );
    const csv = [headers.join(","), ...csvRows].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "moodlight_data.csv";
    a.click();
    URL.revokeObjectURL(url);
  }, [rows]);

  const sortArrow = (key: SortKey) => {
    if (sortBy !== key) return "";
    return sortAsc ? " \u25B2" : " \u25BC";
  };

  if (isLoading) {
    return (
      <div>
        <h2 className="mb-1 text-lg font-semibold">World View</h2>
        <div className="h-96 animate-pulse rounded bg-muted" />
      </div>
    );
  }

  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <h2 className="text-lg font-semibold">
          World View{" "}
          <span className="text-sm font-normal text-muted-foreground">
            ({rows.length} posts, last 72h)
          </span>
        </h2>
        <Button
          variant="outline"
          size="sm"
          className="text-xs"
          onClick={handleExport}
        >
          Export CSV
        </Button>
      </div>
      <p className="mb-3 text-xs text-muted-foreground">
        Everything happening right now&mdash;the raw intelligence feed.
      </p>

      {rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No recent data available.
        </p>
      ) : (
        <div className="max-h-[600px] overflow-auto rounded-lg border border-border">
          <table className="w-full min-w-[640px] table-fixed text-xs">
            <colgroup>
              <col className="w-[53%]" />
              <col className="w-[8%]" />
              <col className="w-[10%]" />
              <col className="w-[10%]" />
              <col className="w-[10%]" />
              <col className="w-[9%]" />
            </colgroup>
            <thead className="sticky top-0 bg-card">
              <tr className="border-b border-border text-left">
                <th
                  className="cursor-pointer p-2 hover:text-foreground"
                  onClick={() => handleSort("created_at")}
                >
                  Post{sortArrow("created_at")}
                </th>
                <th
                  className="cursor-pointer p-2 hover:text-foreground"
                  onClick={() => handleSort("source")}
                >
                  Source{sortArrow("source")}
                </th>
                <th
                  className="cursor-pointer p-2 hover:text-foreground"
                  onClick={() => handleSort("topic")}
                >
                  Topic{sortArrow("topic")}
                </th>
                <th
                  className="cursor-pointer p-2 hover:text-foreground"
                  onClick={() => handleSort("empathy_score")}
                >
                  Empathy{sortArrow("empathy_score")}
                </th>
                <th className="p-2">Emotion</th>
                <th className="p-2 text-right">Posted</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr
                  key={i}
                  className="border-b border-border/50 hover:bg-muted/30"
                >
                  <td className="p-2">
                    <span className="line-clamp-4 leading-relaxed">
                      {r.text}
                    </span>
                  </td>
                  <td className="truncate p-2">{r.source}</td>
                  <td className="truncate p-2">{r.topic}</td>
                  <td className="truncate p-2">{r.empathy_label}</td>
                  <td className="truncate p-2 capitalize">
                    {r.emotion || "\u2014"}
                  </td>
                  <td className="whitespace-nowrap p-2 text-right">
                    {r.created_display}
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
