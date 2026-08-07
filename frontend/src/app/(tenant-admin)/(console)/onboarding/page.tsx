"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { ChatBubble } from "@/components/ui/ChatBubble";
import { StreamingText } from "@/components/ui/StreamingText";
import { apiFetch, ApiError } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface OnboardingStateResponse {
  stage: string;
  prompt: string;
  draft: Record<string, Record<string, unknown>>;
  completed: boolean;
}

interface Message {
  role: "assistant" | "customer";
  text: string;
  streaming?: boolean;
}

const STAGE_LABELS: Record<string, string> = {
  identity: "About your business",
  tone: "Voice and tone",
  services: "Services and products",
  pricing_rules: "Pricing rules",
  escalation_threshold: "Escalation threshold",
};

function formatServices(draft: unknown): string | null {
  if (!draft || typeof draft !== "object") return null;
  const d = draft as Record<string, unknown>;
  const items = d.items as Array<Record<string, unknown>> | undefined;
  if (!items || items.length === 0) return null;
  return items
    .map((item) => {
      const name = item.name ?? "Unknown";
      const price = item.price_dollars != null ? ` at $${item.price_dollars}` : " (no price)";
      return `${name}${price}`;
    })
    .join(", ");
}

function formatPricingRules(draft: unknown): string | null {
  if (!draft || typeof draft !== "object") return null;
  const d = draft as Record<string, unknown>;
  const rules = d.rules as Array<Record<string, unknown>> | undefined;
  if (!rules || rules.length === 0) return null;
  return rules
    .map((r) => {
      const label = r.label ?? r.code ?? "Unknown";
      const amount = r.unit_amount_dollars != null ? `, $${r.unit_amount_dollars}/${r.unit ?? "each"}` : " (no price)";
      return `${label}${amount}`;
    })
    .join(", ");
}

function formatIdentity(draft: unknown): string | null {
  if (!draft || typeof draft !== "object") return null;
  const d = draft as Record<string, unknown>;
  return (d.description as string) || null;
}

function formatTone(draft: unknown): string | null {
  if (!draft || typeof draft !== "object") return null;
  return (draft as Record<string, unknown>).tone as string || null;
}

function formatEscalation(draft: unknown): string | null {
  if (!draft || typeof draft !== "object") return null;
  const d = draft as Record<string, unknown>;
  const posture = d.posture as string | undefined;
  const threshold = d.threshold as number | undefined;
  if (posture) return posture.charAt(0).toUpperCase() + posture.slice(1);
  if (threshold != null) return `Threshold: ${threshold}`;
  return null;
}

const FORMATTERS: Record<string, (draft: unknown) => string | null> = {
  identity: formatIdentity,
  tone: formatTone,
  services: formatServices,
  pricing_rules: formatPricingRules,
  escalation_threshold: formatEscalation,
};

/**
 * Parses an onboarding SSE data payload. Returns null for malformed frames.
 */
function parseOnboardingEvent(payload: string): {
  type: string;
  text?: string;
  draft?: Record<string, Record<string, unknown>>;
  completed?: boolean;
  detail?: string;
} | null {
  try {
    const parsed = JSON.parse(payload);
    if (parsed && typeof parsed === "object" && typeof parsed.type === "string") {
      return parsed;
    }
  } catch { /* skip */ }
  return null;
}

/**
 * T-006 / T-042: the Copilot onboarding chat. Chat pane on the left with SSE
 * streaming, live formatted summary panel on the right showing what is captured
 * and what is still missing. The stage-based state machine is retired; the
 * copilot now uses the agentic loop under the hood, but the frontend contract
 * remains the same.
 */
export default function OnboardingPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState<Record<string, Record<string, unknown>>>({});
  const [completed, setCompleted] = useState(false);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    apiFetch<OnboardingStateResponse>("/api/onboarding/state")
      .then((state) => {
        setDraft(state.draft);
        setCompleted(state.completed);
        if (!state.completed) {
          setMessages([{ role: "assistant", text: state.prompt }]);
        }
      })
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Failed to load onboarding"))
      .finally(() => setLoaded(true));
  }, []);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    setError(null);
    setBusy(true);
    setInput("");
    setMessages((prev) => [
      ...prev,
      { role: "customer", text: trimmed },
      { role: "assistant", text: "", streaming: true },
    ]);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch(`${API_URL}/api/onboarding/message/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: trimmed }),
        signal: controller.signal,
      });
      if (!res.ok || !res.body) throw new Error("onboarding request failed");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() ?? "";

        for (const raw of events) {
          if (!raw.startsWith("data: ")) continue;
          const event = parseOnboardingEvent(raw.slice("data: ".length));
          if (!event) continue;

          switch (event.type) {
            case "progress":
              break; // processing indicator - no visible change needed
            case "reply":
              if (event.text) {
                setMessages((prev) => {
                  const next = [...prev];
                  const last = next[next.length - 1];
                  if (last && last.role === "assistant") {
                    next[next.length - 1] = { ...last, text: event.text!, streaming: false };
                  }
                  return next;
                });
              }
              break;
            case "state":
              if (event.draft) setDraft(event.draft);
              if (event.completed) setCompleted(event.completed);
              break;
            case "done":
              setMessages((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                if (last && last.role === "assistant") {
                  next[next.length - 1] = { ...last, streaming: false };
                }
                return next;
              });
              break;
            case "error":
              setError(event.detail ?? "Something went wrong");
              break;
          }
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last && last.role === "assistant" && !last.text) return prev.slice(0, -1);
          return prev;
        });
      } else {
        setError(err instanceof Error ? err.message : "Something went wrong");
      }
    } finally {
      abortRef.current = null;
      setBusy(false);
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void send(input);
  }

  async function handleConfirm() {
    setError(null);
    setBusy(true);
    try {
      await apiFetch("/api/onboarding/confirm", { method: "POST" });
      setCompleted(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  const capturedKeys = Object.keys(draft);
  const isConfirmReady = !completed && capturedKeys.length >= 5;

  if (!loaded) {
    return <main className="flex flex-1 items-center justify-center p-8" />;
  }

  return (
    <main className="flex min-h-screen flex-col gap-6 p-8 lg:flex-row">
      <section className="flex flex-1 flex-col rounded-lg border border-border bg-surface p-6">
        <h1 className="text-title-2 font-semibold text-text">Onboarding</h1>
        <p className="mt-1 text-body-sm text-text-secondary">
          Answer a few questions and your assistant will be ready to go live.
        </p>

        <div className="mt-6 flex flex-1 flex-col gap-3 overflow-y-auto">
          {completed ? (
            <ChatBubble role="system">You are live! Onboarding is complete.</ChatBubble>
          ) : (
            messages.map((message, index) => (
              <ChatBubble key={index} role={message.role}>
                <StreamingText streaming={message.streaming ?? false}>
                  {message.text || (message.streaming ? "" : "…")}
                </StreamingText>
              </ChatBubble>
            ))
          )}
        </div>

        {!completed ? (
          <form onSubmit={handleSubmit} className="mt-6 flex gap-2">
            <div className="flex-1">
              <Input
                label="Your reply"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={busy}
                autoFocus
              />
            </div>
            <Button type="submit" loading={busy}>
              Send
            </Button>
          </form>
        ) : null}

        {!completed && isConfirmReady ? (
          <div className="mt-4">
            <Button onClick={handleConfirm} loading={busy}>
              Confirm and go live
            </Button>
          </div>
        ) : null}

        {error ? <p className="mt-3 text-footnote text-danger">{error}</p> : null}
      </section>

      <aside className="w-full rounded-lg border border-border bg-surface p-6 lg:w-80">
        <h2 className="text-title-3 font-semibold text-text">Captured so far</h2>
        <ul className="mt-4 flex flex-col gap-3">
          {Object.entries(STAGE_LABELS).map(([key, label]) => {
            const captured = key in draft;
            const formatted = captured ? FORMATTERS[key]?.(draft[key]) : null;
            return (
              <li key={key} className="text-body-sm">
                <span className="font-medium text-text">{label}</span>
                {captured && formatted ? (
                  <p className="text-text-secondary">{formatted}</p>
                ) : captured ? (
                  <p className="text-text-secondary italic">Captured</p>
                ) : (
                  <p className="text-text-tertiary italic">Not yet captured</p>
                )}
              </li>
            );
          })}
        </ul>
      </aside>
    </main>
  );
}
