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
  const [sharpen, setSharpen] = useState<{ options: string[]; original: string } | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  async function send(text: string, skipSharpen = false) {
    if (!text.trim() || loading) return;
    setSharpen(null);
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
        }),
      });
      const data = await res.json();
      // Thin-query sharpener: vague query returned richer premises to pick from.
      if (data.sharpen_options && data.sharpen_options.length) {
        setSharpen({ options: data.sharpen_options, original: text });
      } else {
        addMessage({
          role: "assistant",
          content: data.response || data.answer || JSON.stringify(data),
        });
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
                  onClick={() => send(opt, true)}
                  className="rounded-lg border border-border bg-muted/50 px-3 py-2 text-left text-sm transition-colors hover:border-primary"
                >
                  {opt}
                </button>
              ))}
              <button
                type="button"
                onClick={() => send(sharpen.original, true)}
                className="text-left text-xs text-muted-foreground underline"
              >
                Ask what I typed anyway
              </button>
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
