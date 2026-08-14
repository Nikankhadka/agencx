"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { ChatBubble } from "@/components/ui/ChatBubble";
import { Sheet } from "@/components/ui/Sheet";
import { StreamingText } from "@/components/ui/StreamingText";
import { apiFetch, apiFetchStream, ApiError } from "@/lib/api";
import {
  foldReply,
  parseOnboardingEvent,
  type InputSpec,
  type OnboardingDraft,
  type OnboardingState,
} from "@/lib/onboarding";
import { BeatComposer } from "./components/BeatComposer";
import { ShowBack } from "./components/ShowBack";

interface Message {
  role: "assistant" | "customer";
  text: string;
  streaming?: boolean;
}

/** A state snapshot without history[] - the SSE ``state`` event carries these. */
interface StateFields {
  stage: string;
  draft: OnboardingDraft;
  completed: boolean;
  input: InputSpec | null;
  can_confirm: boolean;
}

function historyToMessages(
  history: { role: string; content: string }[] | undefined,
): Message[] {
  return (history ?? []).map((message) => ({
    role: message.role === "user" ? "customer" : "assistant",
    text: message.content,
  }));
}

/**
 * T-057: the onboarding interview, rebuilt around the server's beat system.
 * A bare-prose thread on the right; the "show-back" (what the assistant has
 * captured) is a desktop aside, and on mobile it lives in a bottom Business
 * Sheet opened from the header. The composer renders whatever widget the
 * server's InputSpec asks for (BeatComposer); confirm is server-gated via
 * ``can_confirm`` rather than a client-side draft-length guess.
 */
export default function OnboardingPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState<OnboardingDraft>({});
  const [completed, setCompleted] = useState(false);
  const [stage, setStage] = useState("");
  const [input, setInput] = useState<InputSpec | null>(null);
  const [canConfirm, setCanConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  function applyStateFields(fields: StateFields) {
    setDraft(fields.draft);
    setCompleted(fields.completed);
    setStage(fields.stage);
    setInput(fields.input);
    setCanConfirm(fields.can_confirm);
  }

  useEffect(() => {
    apiFetch<OnboardingState>("/api/onboarding/state")
      .then((state) => {
        applyStateFields(state);
        const restored = historyToMessages(state.history);
        if (restored.length > 0) {
          setMessages(restored);
        } else if (!state.completed) {
          setMessages([{ role: "assistant", text: state.prompt }]);
        }
      })
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Failed to load onboarding"))
      .finally(() => setLoaded(true));
  }, []);

  function updateLastAssistant(update: (last: Message) => Partial<Message>) {
    setMessages((prev) => {
      const next = [...prev];
      const last = next[next.length - 1];
      if (last && last.role === "assistant") next[next.length - 1] = { ...last, ...update(last) };
      return next;
    });
  }

  async function sendText(text: string) {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    setError(null);
    setBusy(true);
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
      let reply = "";

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
            case "token":
            case "redraft":
            case "reply":
              reply = foldReply(reply, event);
              updateLastAssistant(() => ({ text: reply }));
              break;
            case "state":
              applyStateFields(event);
              break;
            case "done":
              updateLastAssistant(() => ({ streaming: false }));
              break;
            case "error":
              updateLastAssistant(() => ({ streaming: false }));
              setError(event.detail ?? "Something went wrong");
              break;
          }
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        // Stop before the first token leaves an empty bubble - drop it.
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last && last.role === "assistant" && last.text === "") return prev.slice(0, -1);
          const next = [...prev];
          if (last) next[next.length - 1] = { ...last, streaming: false };
          return next;
        });
      } else {
        setError(err instanceof ApiError ? err.detail : "Something went wrong");
      }
    } finally {
      abortRef.current = null;
      setBusy(false);
    }
  }

  async function sendSelection(values: string[]) {
    if (busy || !stage) return;
    setError(null);
    setBusy(true);
    try {
      const state = await apiFetch<OnboardingState>("/api/onboarding/message", {
        method: "POST",
        body: JSON.stringify({ selection: { beat: stage, values } }),
      });
      applyStateFields(state);
      setMessages(historyToMessages(state.history));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  function handleStop() {
    abortRef.current?.abort();
  }

  async function handleConfirm() {
    setError(null);
    setBusy(true);
    try {
      await apiFetch("/api/onboarding/confirm", { method: "POST" });
      setCompleted(true);
      setCanConfirm(false);
      setInput(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  if (!loaded) {
    return (
      <main className="flex flex-1 items-center justify-center p-8">
        <div aria-busy="true" className="h-8 w-8 animate-pulse rounded-full bg-surface-container" />
      </main>
    );
  }

  return (
    <main className="flex min-h-0 flex-1 flex-col px-4 py-6 sm:px-6 lg:py-10">
      <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 lg:flex-row">
        <aside className="hidden shrink-0 lg:block lg:w-72">
          <div className="rounded-card border border-border bg-surface p-4 shadow-card">
            <ShowBack draft={draft} completed={completed} />
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex items-start justify-between gap-3">
            <div className="flex flex-col gap-1">
              <h1 className="text-title-2 font-semibold text-text">Onboarding</h1>
              <p className="text-body-sm text-text-secondary">
                Answer a few questions and your assistant will be ready to go live.
              </p>
            </div>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => setSheetOpen(true)}
              className="lg:hidden"
              data-testid="onboarding-show-back"
            >
              Your business
            </Button>
          </div>

          <div
            className="mt-6 flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto"
            data-testid="onboarding-thread"
          >
            {completed ? (
              <ChatBubble role="system">You are live! Onboarding is complete.</ChatBubble>
            ) : (
              messages.map((message, index) => (
                <ChatBubble key={index} role={message.role}>
                  <StreamingText
                    streaming={message.streaming ?? false}
                    pending={message.streaming === true && !message.text}
                  >
                    {message.text || (message.streaming ? "" : "…")}
                  </StreamingText>
                </ChatBubble>
              ))
            )}
          </div>

          {!completed && canConfirm ? (
            <div className="mt-6">
              <Button
                onClick={handleConfirm}
                loading={busy}
                data-testid="onboarding-confirm"
              >
                Confirm and go live
              </Button>
            </div>
          ) : !completed && input ? (
            <div className="mt-6">
              {/* Mounted unconditionally (only the text toggles) - screen
                  readers reliably announce changes inside an existing live
                  region, but often miss one that appears and disappears. */}
              <p className="h-4 text-footnote text-text-secondary" aria-live="polite">
                {busy ? "Thinking…" : ""}
              </p>
              <BeatComposer
                key={stage}
                input={input}
                busy={busy}
                onText={(text) => void sendText(text)}
                onSelect={(values) => void sendSelection(values)}
                onStop={handleStop}
              />
            </div>
          ) : null}

          {error ? (
            <p className="mt-3 text-footnote text-danger" data-testid="onboarding-error">
              {error}
            </p>
          ) : null}
        </div>
      </div>

      <Sheet open={sheetOpen} onClose={() => setSheetOpen(false)} title="Your business">
        <ShowBack draft={draft} completed={completed} />
      </Sheet>
    </main>
  );
}
