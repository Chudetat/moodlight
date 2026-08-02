"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Send, Loader2, Trash2 } from "lucide-react";
import { FeatureGate } from "@/components/layout/feature-gate";
import { useChatStore } from "@/store/chat-store";
import { useAuth } from "@/lib/hooks/use-auth";

// Pressure-test follow-up (mirrors the widget): strengthens the read — handles the
// strongest objection, names the real downside, gives 2-3 ways to play it — without
// second-guessing it. Relies on conversation_history for "the read above".
const PRESSURE_TEST_PROMPT =
  "Deepen the read above without undermining it. Three things: (1) take the strongest objection a skeptic would raise, then HANDLE it — say why the call still holds, or name the one condition that would flip it; don't leave the objection hanging. (2) the real downside to manage if the read is right. (3) 2-3 distinct ways to play it, with the tradeoff on each. Keep the conviction of the original read intact — this is stress-testing it, not second-guessing it. Keep it tight.";

function ChatContent() {
  const { username } = useAuth();
  const { messages, addMessage, clearMessages } = useChatStore();
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sharpen, setSharpen] = useState<{ options: string[]; original: string; pool: string[] } | null>(null);
  const [explore, setExplore] = useState<{ options: string[] } | null>(null);
  const explorePool = useRef<string[]>([]);
  // Post-answer affordances (pressure-test always; brand bridge only when the answer
  // isn't already about a specific brand). `brand` = the detected brand for the last
  // answer, from search_info; empty string means "cultural/topic answer".
  const [postAnswer, setPostAnswer] = useState<{ brand: string } | null>(null);
  const [bridgeOpen, setBridgeOpen] = useState(false);
  const [bridgeValue, setBridgeValue] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const lastMsgRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;
    const last = messages[messages.length - 1];
    // Mirror the widget: land at the TOP of a new answer so it reads from the
    // start, instead of jumping to the bottom (past the output to the explore/
    // brand trays below). The user's own message still scrolls to the bottom.
    if (last?.role === "assistant" && lastMsgRef.current) {
      requestAnimationFrame(() => {
        const el = lastMsgRef.current;
        if (!el) return;
        container.scrollTop +=
          el.getBoundingClientRect().top - container.getBoundingClientRect().top;
      });
    } else {
      container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
    }
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

  async function send(text: string, skipSharpen = false, pick?: string, original?: string, label?: string) {
    if (!text.trim() || loading) return;
    const prevTray = sharpen?.options || [];
    const prevPool = sharpen?.pool || [];
    setSharpen(null);
    setExplore(null);
    setPostAnswer(null);
    setBridgeOpen(false);
    setBridgeValue("");
    if (!pick) explorePool.current = [];
    // Crafted actions (pressure-test, brand bridge) show a clean label in the thread,
    // not the long prompt actually sent to the model.
    addMessage({ role: "user", content: label ?? text });
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
        // Post-answer affordances: pressure-test on every answer; brand bridge only
        // when the answer isn't already about a specific brand (search_info.brand).
        setPostAnswer({ brand: (data.search_info && data.search_info.brand) || "" });
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

  // Pressure-test the last answer — the go-deeper utility (folded alongside explore).
  function pressureTest() {
    void send(PRESSURE_TEST_PROMPT, true, undefined, undefined, "Pressure-test & options →");
  }

  // Brand bridge: connect the cultural read above to the user's own brand, grounded
  // in that brand's live signal. Mirrors the widget's crafted bridge query.
  function submitBridge() {
    const brand = bridgeValue.trim();
    if (!brand) return;
    const q =
      `How does the cultural pattern above apply specifically to ${brand}? Using ${brand}'s own tracked signal, ` +
      `give the real implications for ${brand} and the concrete moves it should make — connect the culture to the ` +
      `brand, grounded in ${brand}'s actual situation, not a generic trend read.`;
    void send(q, true, undefined, undefined, `What does this mean for ${brand}?`);
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
            ref={i === messages.length - 1 ? lastMsgRef : undefined}
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
        {postAnswer && !loading && !sharpen && (
          <div className="flex justify-start">
            <div className="flex flex-col gap-2" style={{ maxWidth: "90%" }}>
              {/* Go deeper: pressure-test the read (objection-handling, not self-refute) */}
              <button
                type="button"
                onClick={pressureTest}
                className="self-start rounded-full border border-border px-4 py-1.5 text-xs text-muted-foreground transition-colors hover:border-primary hover:text-foreground"
              >
                Pressure-test &amp; options →
              </button>
              {/* Brand bridge — only when the answer isn't already about a specific brand */}
              {!postAnswer.brand &&
                (bridgeOpen ? (
                  <div className="flex flex-col gap-1.5">
                    <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                      Your brand or business
                    </span>
                    <div className="flex gap-2">
                      <Input
                        autoFocus
                        value={bridgeValue}
                        onChange={(e) => setBridgeValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            submitBridge();
                          }
                        }}
                        placeholder="e.g. Modelo, or your company"
                        maxLength={120}
                        className="flex-1"
                      />
                      <Button type="button" onClick={submitBridge} disabled={!bridgeValue.trim()}>
                        Go
                      </Button>
                    </div>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => setBridgeOpen(true)}
                    className="self-start rounded-lg border border-primary bg-primary/5 px-3 py-2 text-left text-sm font-medium text-primary transition-colors hover:bg-primary/10"
                  >
                    What does this mean for my brand? →
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
            onClick={() => {
              clearMessages();
              setSharpen(null);
              setExplore(null);
              setPostAnswer(null);
              setBridgeOpen(false);
              setBridgeValue("");
            }}
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
