"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2 } from "lucide-react";

export function BriefGenerator() {
  const [userNeed, setUserNeed] = useState("");
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState("");

  async function generate(e: React.FormEvent) {
    e.preventDefault();
    if (!userNeed.trim()) return;
    setLoading(true);
    setResult("");
    try {
      const res = await fetch("/api/proxy/api/strategic-brief", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_need: userNeed.trim(),
          email_recipient: email || undefined,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        setResult(data.email_sent ? "Brief generated and emailed." : "Brief generated.");
      } else {
        setResult(data.detail || "Error generating brief.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-2">
      <Label className="text-xs text-muted-foreground">
        Strategic Brief
      </Label>
      <form onSubmit={generate} className="space-y-2">
        <Input
          value={userNeed}
          onChange={(e) => setUserNeed(e.target.value)}
          placeholder="What do you need?"
          className="h-7 text-xs"
        />
        <Input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email (optional)"
          className="h-7 text-xs"
        />
        <Button type="submit" size="sm" className="w-full" disabled={loading || !userNeed.trim()}>
          {loading ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : null}
          Generate Brief
        </Button>
      </form>
      {result && (
        <p className="text-xs text-muted-foreground">{result}</p>
      )}
    </div>
  );
}
