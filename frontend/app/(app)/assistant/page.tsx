"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { BrainCircuit, Send, ShieldCheck, Sparkles, UserRound } from "lucide-react";
import { api } from "@/lib/api";
import type { ChatResponse } from "@/lib/types";
import { Badge, Button, Card, PageHeader, PageSkeleton } from "@/components/ui";
import { cn } from "@/lib/format";

type Capabilities = {
  mode: string;
  model: string | null;
  can_answer_about: string[];
  will_not_do: string[];
  disclaimer: string;
};

type Message = {
  id: number;
  role: "user" | "assistant";
  text: string;
  suggestions?: string[];
  grounding?: Record<string, unknown>;
  mode?: string;
  disclaimer?: string;
  error?: boolean;
};

const STARTERS = [
  "Summarise my recent driving events.",
  "Which drivers should I coach first?",
  "Explain how the safety score is calculated.",
  "What does the risk score actually mean?",
];

export default function AssistantPage() {
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [driverId, setDriverId] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void (async () => {
      try {
        setCapabilities(await api.get<Capabilities>("/assistant/capabilities"));
      } catch {
        setCapabilities(null);
      }
    })();
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || sending) return;
    setInput("");
    setMessages((current) => [...current, { id: Date.now(), role: "user", text: trimmed }]);
    setSending(true);
    try {
      const payload: Record<string, unknown> = { message: trimmed, include_fleet_context: true };
      if (driverId) payload.driver_id = Number(driverId);
      const response = await api.post<ChatResponse>("/assistant/chat", payload);
      setMessages((current) => [
        ...current,
        {
          id: Date.now() + 1,
          role: "assistant",
          text: response.reply,
          suggestions: response.suggestions,
          grounding: response.grounding,
          mode: response.mode,
          disclaimer: response.disclaimer,
        },
      ]);
    } catch (err) {
      setMessages((current) => [
        ...current,
        {
          id: Date.now() + 1,
          role: "assistant",
          text: err instanceof Error ? err.message : "The assistant could not be reached.",
          error: true,
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    void send(input);
  };

  if (!capabilities) return <PageSkeleton cards={2} />;

  return (
    <div>
      <PageHeader
        eyebrow="Workspace · AI coach"
        title="AI assistant"
        description="Answers grounded in your own safety data. When no LLM key is configured it runs in a transparent local mode."
        actions={
          <Badge tone={capabilities.mode === "llm" ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300" : "bg-indigo-50 text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-300"}>
            {capabilities.mode === "llm" ? `LLM mode · ${capabilities.model ?? "unknown model"}` : "Local mode · no external model"}
          </Badge>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_330px]">
        <Card padded={false} className="flex min-h-[560px] flex-col">
          <div className="flex items-center gap-3 border-b border-ink-100 px-5 py-3.5 dark:border-white/5">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand-400 to-indigo-500 text-white">
              <BrainCircuit className="h-4 w-4" />
            </span>
            <div>
              <p className="text-sm font-semibold text-ink-900 dark:text-white">SafeWay Coach</p>
              <p className="text-[10px] text-ink-400">Grounded in recorded events, scores and risk assessments</p>
            </div>
            <span className="ml-auto flex items-center gap-1.5 text-[10px] text-ink-400">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> {capabilities.mode === "llm" ? "LLM connected" : "Local rule-based responses"}
            </span>
          </div>

          <div className="flex-1 space-y-4 overflow-y-auto p-5">
            {messages.length === 0 && (
              <div className="flex h-full flex-col items-center justify-center py-10 text-center">
                <span className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-300">
                  <Sparkles className="h-6 w-6" />
                </span>
                <h2 className="text-sm font-semibold text-ink-900 dark:text-white">Ask about your fleet</h2>
                <p className="mt-1 max-w-sm text-xs leading-relaxed text-ink-500 dark:text-ink-400">
                  Try a question below. Answers cite the data they used and always carry a disclaimer.
                </p>
                <div className="mt-5 grid w-full max-w-md gap-2">
                  {STARTERS.map((starter) => (
                    <button
                      key={starter}
                      onClick={() => void send(starter)}
                      className="rounded-xl border border-ink-200 bg-white px-3.5 py-2.5 text-left text-xs text-ink-700 transition hover:border-brand-400 hover:bg-brand-50/60 dark:border-white/10 dark:bg-white/5 dark:text-ink-200 dark:hover:border-brand-500/40"
                    >
                      {starter}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((message) => (
              <motion.div
                key={message.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25 }}
                className={cn("flex gap-3", message.role === "user" && "flex-row-reverse")}
              >
                <span
                  className={cn(
                    "flex h-8 w-8 shrink-0 items-center justify-center rounded-xl",
                    message.role === "user"
                      ? "bg-ink-100 text-ink-600 dark:bg-white/10 dark:text-ink-200"
                      : message.error
                        ? "bg-rose-50 text-rose-600 dark:bg-rose-500/10"
                        : "bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-300",
                  )}
                >
                  {message.role === "user" ? <UserRound className="h-4 w-4" /> : <BrainCircuit className="h-4 w-4" />}
                </span>
                <div className={cn("max-w-[85%] space-y-2", message.role === "user" && "text-right")}>
                  <div
                    className={cn(
                      "rounded-2xl px-4 py-3 text-xs leading-relaxed",
                      message.role === "user"
                        ? "bg-brand-600 text-white"
                        : message.error
                          ? "border border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200"
                          : "border border-ink-100 bg-ink-50 text-ink-800 dark:border-white/10 dark:bg-white/5 dark:text-ink-100",
                    )}
                  >
                    <p className="whitespace-pre-wrap">{message.text}</p>
                  </div>

                  {message.suggestions && message.suggestions.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {message.suggestions.map((suggestion) => (
                        <button
                          key={suggestion}
                          onClick={() => void send(suggestion)}
                          className="rounded-full border border-ink-200 bg-white px-2.5 py-1 text-[10px] text-ink-600 transition hover:border-brand-400 hover:text-brand-700 dark:border-white/10 dark:bg-white/5 dark:text-ink-300 dark:hover:text-brand-300"
                        >
                          {suggestion}
                        </button>
                      ))}
                    </div>
                  )}

                  {message.grounding && (
                    <div className="rounded-lg bg-ink-100/70 px-2.5 py-1.5 text-[10px] text-ink-500 dark:bg-white/5 dark:text-ink-400">
                      Grounding: {String((message.grounding as { context_used?: string[] }).context_used?.join(", ") ?? "recorded telemetry")}
                      {message.mode && <span className="ml-2 uppercase tracking-wide opacity-70">{message.mode}</span>}
                    </div>
                  )}
                </div>
              </motion.div>
            ))}

            {sending && (
              <div className="flex gap-3">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-300">
                  <BrainCircuit className="h-4 w-4" />
                </span>
                <div className="flex gap-1 rounded-2xl border border-ink-100 bg-ink-50 px-4 py-3 dark:border-white/10 dark:bg-white/5">
                  {[0, 1, 2].map((dot) => (
                    <span
                      key={dot}
                      className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-400"
                      style={{ animationDelay: `${dot * 120}ms` }}
                    />
                  ))}
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>

          <form onSubmit={submit} className="border-t border-ink-100 p-3 dark:border-white/5">
            <div className="flex items-end gap-2">
              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    void send(input);
                  }
                }}
                rows={1}
                placeholder="Ask about scores, events, coaching or maintenance…"
                className="input max-h-32 min-h-[44px] flex-1 resize-none py-2.5"
              />
              <Button type="submit" loading={sending} className="h-[44px] px-3.5">
                <Send className="h-4 w-4" />
                <span className="sr-only">Send</span>
              </Button>
            </div>
            <p className="mt-2 px-1 text-[10px] text-ink-400">
              Enter to send · Shift+Enter for a new line. Model keys, when configured, stay on the server and are never exposed to this browser.
            </p>
          </form>
        </Card>

        <div className="space-y-4">
          <Card title="Scope" subtitle="Driver context" padded={false}>
            <div className="p-4">
              <label className="block">
                <span className="label">Ask about a specific driver (optional)</span>
                <select
                  value={driverId}
                  onChange={(event) => setDriverId(event.target.value)}
                  className="input"
                  aria-label="Driver context"
                >
                  <option value="">Fleet-wide context</option>
                  <option value="1">Driver #1 (demo)</option>
                  <option value="2">Driver #2 (demo)</option>
                  <option value="3">Driver #3 (demo)</option>
                </select>
              </label>
              <p className="mt-2 text-[10px] leading-relaxed text-ink-400">
                Driver context is resolved on the server within your organisation only. Cross-organisation lookups are rejected.
              </p>
            </div>
          </Card>

          <Card title="This assistant can" subtitle="Grounded capabilities">
            <ul className="space-y-2 text-[11px] leading-relaxed text-ink-600 dark:text-ink-300">
              {capabilities.can_answer_about.map((item) => (
                <li key={item} className="flex gap-2">
                  <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" />
                  {item}
                </li>
              ))}
            </ul>
          </Card>

          <Card title="This assistant will not" subtitle="Hard boundaries">
            <ul className="space-y-2 text-[11px] leading-relaxed text-ink-600 dark:text-ink-300">
              {capabilities.will_not_do.map((item) => (
                <li key={item} className="flex gap-2">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-rose-500" />
                  {item}
                </li>
              ))}
            </ul>
          </Card>

          <Card title="Disclaimer" subtitle="Read before relying on an answer">
            <p className="text-[11px] leading-relaxed text-ink-500 dark:text-ink-400">{capabilities.disclaimer}</p>
            {capabilities.mode !== "llm" && (
              <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-[10px] leading-relaxed text-amber-800 dark:bg-amber-500/10 dark:text-amber-200">
                No LLM provider key is configured on this deployment. Answers are generated locally from template rules
                over your recorded data — they are deterministic and limited in scope, not generative advice.
              </p>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
