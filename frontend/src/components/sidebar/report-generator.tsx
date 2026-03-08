"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2 } from "lucide-react";

export function ReportGenerator() {
  const [subject, setSubject] = useState("");
  const [subjectType, setSubjectType] = useState<"brand" | "topic">("brand");
  const [days, setDays] = useState(7);
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState("");

  async function generate(e: React.FormEvent) {
    e.preventDefault();
    if (!subject.trim()) return;
    setLoading(true);
    setResult("");
    try {
      const res = await fetch("/api/proxy/api/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          subject: subject.trim(),
          subject_type: subjectType,
          days,
          email_recipient: email || undefined,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        setResult(data.email_sent ? "Report generated and emailed." : "Report generated.");
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
      <form onSubmit={generate} className="space-y-2">
        <Input
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          placeholder="Subject (brand or topic)"
          className="h-7 text-xs"
        />
        <div className="flex gap-1.5">
          <Button
            type="button"
            variant={subjectType === "brand" ? "secondary" : "ghost"}
            size="xs"
            onClick={() => setSubjectType("brand")}
          >
            Brand
          </Button>
          <Button
            type="button"
            variant={subjectType === "topic" ? "secondary" : "ghost"}
            size="xs"
            onClick={() => setSubjectType("topic")}
          >
            Topic
          </Button>
        </div>
        <Input
          type="number"
          min={1}
          max={30}
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="h-7 text-xs"
          placeholder="Days"
        />
        <Input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email (optional)"
          className="h-7 text-xs"
        />
        <Button type="submit" size="sm" className="w-full" disabled={loading || !subject.trim()}>
          {loading ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : null}
          Generate
        </Button>
      </form>
      {result && (
        <p className="text-xs text-muted-foreground">{result}</p>
      )}
    </div>
  );
}
