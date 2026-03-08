"use client";

import { useState } from "react";
import { useAuth } from "@/lib/hooks/use-auth";
import { useBrands } from "@/lib/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, Check } from "lucide-react";

const TIME_OPTIONS = [
  { value: 7, label: "Last 7 days" },
  { value: 14, label: "Last 14 days" },
  { value: 30, label: "Last 30 days" },
];

export function ReportGenerator() {
  const { username } = useAuth();
  const { data: brandsData } = useBrands(username);
  const brands = brandsData?.brands ?? [];

  const [selection, setSelection] = useState<string>("custom");
  const [customTopic, setCustomTopic] = useState("");
  const [days, setDays] = useState(7);
  const [emailMe, setEmailMe] = useState(false);
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState("");

  const subject = selection === "custom" ? customTopic.trim() : selection;

  async function generate(e: React.FormEvent) {
    e.preventDefault();
    if (!subject) return;
    setLoading(true);
    setResult("");
    try {
      const res = await fetch("/api/proxy/api/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          subject,
          subject_type: selection === "custom" ? "topic" : "brand",
          days,
          email_recipient: emailMe ? email || undefined : undefined,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        setResult(
          data.email_sent
            ? "Report generated and emailed."
            : "Report generated."
        );
      } else {
        setResult(data.detail || "Error generating report.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-2">
      <Label className="text-xs text-muted-foreground">
        Intelligence Report
      </Label>
      <p className="text-[10px] text-muted-foreground">
        Generate deep-dive reports on any brand or topic
      </p>
      <form onSubmit={generate} className="space-y-2">
        {/* Subject selector */}
        <select
          value={selection}
          onChange={(e) => setSelection(e.target.value)}
          className="h-7 w-full rounded-md border border-input bg-transparent px-2 text-xs"
        >
          <option value="custom">Custom topic...</option>
          {brands.map((b) => (
            <option key={b} value={b}>
              {b}
            </option>
          ))}
        </select>

        {/* Custom topic input */}
        {selection === "custom" && (
          <Input
            value={customTopic}
            onChange={(e) => setCustomTopic(e.target.value)}
            placeholder="e.g. Tesla, AI regulation, tariffs"
            className="h-7 text-xs"
          />
        )}

        {/* Time period */}
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="h-7 w-full rounded-md border border-input bg-transparent px-2 text-xs"
        >
          {TIME_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        {/* Email checkbox */}
        <label className="flex items-center gap-2 text-xs">
          <button
            type="button"
            onClick={() => setEmailMe(!emailMe)}
            className={`flex h-4 w-4 items-center justify-center rounded border ${
              emailMe
                ? "border-primary bg-primary text-primary-foreground"
                : "border-input"
            }`}
          >
            {emailMe && <Check className="h-3 w-3" />}
          </button>
          Email report to me
        </label>

        {emailMe && (
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
            className="h-7 text-xs"
          />
        )}

        <Button
          type="submit"
          size="sm"
          className="w-full"
          disabled={loading || !subject}
        >
          {loading ? (
            <Loader2 className="mr-1 h-3 w-3 animate-spin" />
          ) : null}
          Generate Report
        </Button>
      </form>
      {result && (
        <p className="text-xs text-muted-foreground">{result}</p>
      )}
    </div>
  );
}
