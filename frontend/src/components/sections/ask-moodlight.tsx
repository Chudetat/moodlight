"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Send, Loader2, Trash2 } from "lucide-react";
import { FeatureGate } from "@/components/layout/feature-gate";
import { useChatStore } from "@/store/chat-store";
import { useAuth } from "@/lib/hooks/use-auth";

function ChatContent() {
  const { username } = useAuth();
  const { messages, addMessage, clearMessages } = useChatStore();
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sharpen, setSharpen] = useState<{ options: string[]; original: string; pool: string[] } | null>(null);
  const [explore, setExplore] = useState<{ options: string[] } | null>(null);
  const explorePool = useRef<string[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  // Exploration loop: after a sharpened pick is answered, re-offer the unpicked
  // angles + one freshly generated (excluding all shown), keeping the tray at three.
  async function refreshSharpen(
    pickedText: string,
    prevTray: string[],
    prevPool: string[],
    original: string,
  ) {
    const leftovers = prevTray.filter((o) => o !== pickedText);
    let extra: string[] = [];
    try {
      const res = await fetch("/api/proxy/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: original,
          username: username || "admin",
          conversation_history: [],
          sharpen_more: true,
          sharpen_original: original,
          sharpen_exclude: prevPool,
        }),
      });
      const d = await res.json();
      extra = d.sharpen_options || [];
    } catch {}
    const tray = [...leftovers, ...extra].slice(0, 3);
    if (tray.length) setSharpen({ options: tray, original, pool: [...prevPool, ...extra] });
  }

  // Explore-next: after any answer, offer sharp NEXT angles drawn from that answer's
  // live-signal intelligence (grounded, never generic). Loops as the user picks.
  async function exploreNext(question: string, answer: string) {
    if (!answer) return;
    const pool = explorePool.current;
    let opts: string[] = [];
    try {
      const res = await fetch("/api/proxy/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: question,
          username: username || "admin",
          conversation_history: [],
          sharpen_more: true,
          sharpen_original: question,
          explore_answer: answer,
          sharpen_exclude: pool,
        }),
      });
      const d = await res.json();
      opts = d.sharpen_options || [];
    } catch {}
    if (!opts.length) return;
    explorePool.current = [...pool, ...opts];
    setExplore({ options: opts });
  }

  async function send(text: string, skipSharpen = false, pick?: string, original?: string) {
    if (!text.trim() || loading) return;
    const prevTray = sharpen?.options || [];
    const prevPool = sharpen?.pool || [];
    setSharpen(null);
    setExplore(null);
    if (!pick) explorePool.current = [];
    addMessage({ role: "user", content: text });
    setLoading(true);

    try {
      const res = await fetch("/api/proxy/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          username: username || "admin",
          conversation_history: messages.map((m) => ({
            role: m.role,
            content: m.content,
          })),
          supports_sharpen: true,
          skip_sharpen: skipSharpen,
          sharpen_pick: pick,
          sharpen_original: original,
        }),
      });
      const data = await res.json();
      // Thin-query sharpener: vague query returned richer premises to pick from.
      if (data.sharpen_options && data.sharpen_options.length) {
        setSharpen({ options: data.sharpen_options, original: text, pool: data.sharpen_options });
      } else {
        const answerText = data.response || data.answer || JSON.stringify(data);
        addMessage({ role: "assistant", content: answerText });
        // A thin-query pick re-offers its sibling angles; every other answer gets
        // grounded "explore next" angles drawn from the answer. Fire-and-forget.
        if (pick && pick !== "original" && pick !== "explore") {
          void refreshSharpen(text, prevTray, prevPool, original || text);
        } else if (data.response || data.answer) {
          void exploreNext(text, answerText);
        }
      }
    } catch {
      addMessage({
        role: "assistant",
        content: "Sorry, something went wrong. Please try again.",
      });
    } finally {
      setLoading(false);
    }
  }

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    const userMsg = input.trim();
    if (!userMsg || loading) return;
    setInput("");
    await send(userMsg, false);
  }

  return (
    <div className="flex h-96 flex-col rounded-lg border border-border bg-card">
      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <p className="text-center text-sm text-muted-foreground">
            Ask anything about your intelligence data.
            <br />
            <span className="text-xs">
              e.g. &ldquo;What&rsquo;s happening with NVIDIA?&rdquo;
            </span>
          </p>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${
              msg.role === "user" ? "justify-end" : "justify-start"
            }`}
          >
            <div className="flex flex-col gap-0.5" style={{ maxWidth: "80%" }}>
              <span className="text-[10px] text-muted-foreground">
                {msg.role === "user" ? "You" : "Moodlight"}
              </span>
              <div
                className={`rounded-lg px-3 py-2 text-sm ${
                  msg.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted"
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
              </div>
            </div>
          </div>
        ))}
        {sharpen && !loading && (
          <div className="flex justify-start">
            <div className="flex flex-col gap-2" style={{ maxWidth: "90%" }}>
              <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                Sharpen your ask — pick an angle
              </span>
              {sharpen.options.map((opt, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => send(opt, true, String(i + 1), sharpen.original)}
                  className="rounded-lg border border-border bg-muted/50 px-3 py-2 text-left text-sm transition-colors hover:border-primary"
                >
                  {opt}
                </button>
              ))}
              <button
                type="button"
                onClick={() => send(sharpen.original, true, "original", sharpen.original)}
                className="text-left text-xs text-muted-foreground underline"
              >
                Ask what I typed anyway
              </button>
            </div>
          </div>
        )}
        {explore && !loading && (
          <div className="flex justify-start">
            <div className="flex flex-col gap-2" style={{ maxWidth: "90%" }}>
              <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                Explore next
              </span>
              {explore.options.map((opt, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => send(opt, true, "explore", opt)}
                  className="rounded-lg border border-border bg-muted/50 px-3 py-2 text-left text-sm transition-colors hover:border-primary"
                >
                  {opt}
                </button>
              ))}
            </div>
          </div>
        )}
        {loading && (
          <div className="flex justify-start">
            <div className="flex items-center gap-2 rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" />
              Thinking...
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <form onSubmit={handleSend} className="flex gap-2 border-t border-border p-3">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. What's happening with NVIDIA?"
          className="flex-1"
          disabled={loading}
        />
        <Button type="submit" size="icon" disabled={loading || !input.trim()}>
          <Send className="h-4 w-4" />
        </Button>
        {messages.length > 0 && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={clearMessages}
            title="Clear chat"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        )}
      </form>
    </div>
  );
}

export function AskMoodlight() {
  return (
    <div>
      <h2 className="mb-1 text-lg font-semibold">Ask Moodlight</h2>
      <FeatureGate feature="ask_moodlight">
        <ChatContent />
      </FeatureGate>
    </div>
  );
}
