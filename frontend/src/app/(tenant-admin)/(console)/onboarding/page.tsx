"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { ChatBubble } from "@/components/ui/ChatBubble";
import { StreamingText } from "@/components/ui/StreamingText";
import { Icon } from "@/components/ui/Icon";
import { apiFetch, apiFetchStream, ApiError } from "@/lib/api";

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
 * T-006 / T-042: the Agencx onboarding chat. A single centered column: heading,
 * five stage pills as progress, the SSE-streaming chat, and the composer. The
 * stage-based state machine is retired; the copilot now uses the agentic loop
 * under the hood, but the frontend contract remains the same.
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
      const res = await apiFetchStream("/api/onboarding/message/stream", {
        method: "POST",
        body: JSON.stringify({ text: trimmed }),
        signal: controller.signal,
      });
      if (!res.body) throw new Error("onboarding request failed");

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
              setMessages((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                if (last && last.role === "assistant") {
                  next[next.length - 1] = { ...last, streaming: false };
                }
                return next;
              });
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
        setError(err instanceof ApiError ? err.detail : "Something went wrong");
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
    return (
      <main className="flex flex-1 items-center justify-center p-8">
        <div aria-busy="true" className="h-8 w-8 animate-pulse rounded-full bg-surface-container" />
      </main>
    );
  }

  return (
    <main className="flex flex-1 flex-col items-center px-4 py-6 sm:px-6 lg:py-10">
      <div className="flex w-full max-w-2xl flex-1 flex-col">
        <div className="flex flex-col gap-1">
          <h1 className="text-title-2 font-semibold text-text">Onboarding</h1>
          <p className="text-body-sm text-text-secondary">
            Answer a few questions and your assistant will be ready to go live.
          </p>
        </div>

        <ul className="mt-5 flex flex-wrap gap-2" aria-label="Onboarding progress">
          {Object.entries(STAGE_LABELS).map(([key, label]) => {
            const captured = capturedKeys.includes(key);
            return (
              <li
                key={key}
                className={[
                  "flex items-center gap-1.5 rounded-full border border-border px-3 py-1 text-footnote font-medium",
                  captured ? "text-text" : "text-text-tertiary",
                ].join(" ")}
              >
                <Icon name="check_circle" filled={captured} size={16} />
                {label}
              </li>
            );
          })}
        </ul>

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
      </div>
    </main>
  );
}
