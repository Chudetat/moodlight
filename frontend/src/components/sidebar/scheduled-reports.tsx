"use client";

import { useState } from "react";
import { useAuth } from "@/lib/hooks/use-auth";
import {
  useBrands,
  useReportSchedules,
  useCreateReportSchedule,
  useToggleReportSchedule,
  useDeleteReportSchedule,
} from "@/lib/hooks/use-api";
import { FeatureGate } from "@/components/layout/feature-gate";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export function ScheduledReports() {
  const { username } = useAuth();
  const { data } = useReportSchedules();
  const { data: brandData } = useBrands(username);
  const create = useCreateReportSchedule();
  const toggle = useToggleReportSchedule();
  const remove = useDeleteReportSchedule();
  const [showForm, setShowForm] = useState(false);
  const [subject, setSubject] = useState("");
  const [customSubject, setCustomSubject] = useState("");
  const [frequency, setFrequency] = useState("weekly");
  const [lookback, setLookback] = useState("7");

  if (!username) return null;
  const schedules = data?.schedules ?? [];
  const brands = brandData?.brands ?? [];
  const options = ["Custom topic...", ...brands];
  const finalSubject =
    subject === "Custom topic..." ? customSubject.trim() : subject;

  return (
    <div className="space-y-2">
      <p className="text-xs font-medium uppercase text-muted-foreground">
        Scheduled Reports
      </p>
      <FeatureGate feature="intelligence_reports">
        {schedules.length === 0 && !showForm && (
          <p className="text-xs text-muted-foreground">
            No scheduled reports yet.
          </p>
        )}
        {schedules.map((s) => (
          <div
            key={s.id}
            className="flex items-center justify-between text-sm"
          >
            <div className="flex items-center gap-1">
              <span>{s.enabled ? "\u2705" : "\u23F8\uFE0F"}</span>
              <span className="font-medium">{s.subject}</span>
              <span className="text-xs text-muted-foreground">
                {s.frequency}
              </span>
            </div>
            <div className="flex gap-1">
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-1 text-xs"
                onClick={() =>
                  toggle.mutate({ id: s.id, enabled: !s.enabled })
                }
              >
                {s.enabled ? "Pause" : "Resume"}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-1 text-xs text-destructive"
                onClick={() => remove.mutate(s.id)}
              >
                Delete
              </Button>
            </div>
          </div>
        ))}
        {!showForm ? (
          <Button
            variant="outline"
            size="sm"
            className="w-full text-xs"
            onClick={() => setShowForm(true)}
          >
            Create Schedule
          </Button>
        ) : (
          <div className="space-y-2 rounded border border-border p-2">
            <Select
              value={subject}
              onValueChange={(v) => setSubject(v ?? "")}
            >
              <SelectTrigger className="h-8 text-sm">
                <SelectValue placeholder="Subject" />
              </SelectTrigger>
              <SelectContent>
                {options.map((o) => (
                  <SelectItem key={o} value={o}>
                    {o}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {subject === "Custom topic..." && (
              <Input
                placeholder="Enter topic"
                value={customSubject}
                onChange={(e) => setCustomSubject(e.target.value)}
                className="h-8 text-sm"
              />
            )}
            <Select
              value={frequency}
              onValueChange={(v) => v && setFrequency(v)}
            >
              <SelectTrigger className="h-8 text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="daily">Daily</SelectItem>
                <SelectItem value="weekly">Weekly</SelectItem>
              </SelectContent>
            </Select>
            <Select
              value={lookback}
              onValueChange={(v) => v && setLookback(v)}
            >
              <SelectTrigger className="h-8 text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[7, 14, 30].map((d) => (
                  <SelectItem key={d} value={String(d)}>
                    Last {d} days
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div className="flex gap-1">
              <Button
                size="sm"
                className="flex-1"
                disabled={!finalSubject || create.isPending}
                onClick={() => {
                  if (!finalSubject) return;
                  create.mutate(
                    {
                      subject: finalSubject,
                      subject_type:
                        subject === "Custom topic..." ? "topic" : "brand",
                      frequency,
                      days_lookback: Number(lookback),
                    },
                    {
                      onSuccess: () => {
                        setShowForm(false);
                        setSubject("");
                        setCustomSubject("");
                      },
                    }
                  );
                }}
              >
                Create
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowForm(false)}
              >
                Cancel
              </Button>
            </div>
          </div>
        )}
      </FeatureGate>
    </div>
  );
}
