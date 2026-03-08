"use client";

import { useState } from "react";
import { useAuth } from "@/lib/hooks/use-auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2 } from "lucide-react";

export function BriefGenerator() {
  const { briefCredits } = useAuth();
  const [product, setProduct] = useState("");
  const [audience, setAudience] = useState("");
  const [markets, setMarkets] = useState("");
  const [challenge, setChallenge] = useState("");
  const [timeline, setTimeline] = useState("");
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState("");

  // Assemble user_need from fields (matches Streamlit)
  function buildUserNeed(): string {
    const parts: string[] = [];
    if (product.trim()) parts.push(`launch/promote ${product.trim()}`);
    if (audience.trim()) parts.push(`targeting ${audience.trim()}`);
    if (markets.trim()) parts.push(`in ${markets.trim()}`);
    if (challenge.trim())
      parts.push(`with the challenge of ${challenge.trim()}`);
    if (timeline.trim()) parts.push(`timeline/budget: ${timeline.trim()}`);
    return parts.join(", ");
  }

  async function generate(e: React.FormEvent) {
    e.preventDefault();
    const userNeed = buildUserNeed();
    if (!userNeed) return;
    setLoading(true);
    setResult("");
    try {
      const res = await fetch("/api/proxy/api/strategic-brief", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_need: userNeed,
          email_recipient: email || undefined,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        setResult(
          data.email_sent
            ? "Brief generated and emailed."
            : "Brief generated."
        );
      } else {
        setResult(data.detail || "Error generating brief.");
      }
    } finally {
      setLoading(false);
    }
  }

  const canGenerate = !!product.trim();

  return (
    <div className="space-y-2">
      <Label className="text-xs text-muted-foreground">Strategic Brief</Label>
      <p className="text-[10px] text-muted-foreground">
        The more detail you provide, the better your brief
      </p>
      <form onSubmit={generate} className="space-y-2">
        <Input
          value={product}
          onChange={(e) => setProduct(e.target.value)}
          placeholder='Product / Service — e.g. "premium running shoe"'
          className="h-7 text-xs"
        />
        <Input
          value={audience}
          onChange={(e) => setAudience(e.target.value)}
          placeholder='Target Audience — e.g. "women 25-40, urban"'
          className="h-7 text-xs"
        />
        <Input
          value={markets}
          onChange={(e) => setMarkets(e.target.value)}
          placeholder='Markets / Geography — e.g. "US, UK, Canada"'
          className="h-7 text-xs"
        />
        <Input
          value={challenge}
          onChange={(e) => setChallenge(e.target.value)}
          placeholder='Key Challenge — e.g. "competing against On and Hoka"'
          className="h-7 text-xs"
        />
        <Input
          value={timeline}
          onChange={(e) => setTimeline(e.target.value)}
          placeholder='Timeline / Budget — e.g. "Q1 2025, $2M digital"'
          className="h-7 text-xs"
        />
        {canGenerate && (
          <p className="text-[10px] text-muted-foreground">
            Brief credits:{" "}
            <span className="font-medium">
              {briefCredits === -1 ? "Unlimited" : briefCredits}
            </span>
          </p>
        )}
        <Input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Your email (to receive brief)"
          className="h-7 text-xs"
        />
        <Button
          type="submit"
          size="sm"
          className="w-full"
          disabled={loading || !canGenerate}
        >
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
