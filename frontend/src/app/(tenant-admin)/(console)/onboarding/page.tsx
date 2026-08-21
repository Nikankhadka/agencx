"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import {
  AgentLine,
  LedeMessage,
  OwnerBubble,
  Thread,
  ThreadVeil,
  TypingLine,
} from "@/components/ui/Thread";
import { apiFetch, apiFetchStream, ApiError } from "@/lib/api";
import {
  foldReply,
  parseOnboardingEvent,
  type InputSpec,
  type OnboardingDraft,
  type OnboardingState,
} from "@/lib/onboarding";
import { BeatComposer } from "./components/BeatComposer";

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

/**
 * The prototype's `agentMsg()` holds the typing indicator before a message even
 * when that message is static, so pacing reads the same from the first beat
 * (design/frontend.md section 9). Only the opening message of a fresh
 * conversation is paced - restored history renders at once, per the S1 spec's
 * drop-off/return row.
 */
const OPENING_PACE_MS = 820;

function historyToMessages(
  history: { role: string; content: string }[] | undefined,
): Message[] {
  return (history ?? []).map((message) => ({
    role: message.role === "user" ? "customer" : "assistant",
    text: message.content,
  }));
}

/**
 * The onboarding interview. Ported from the ONBOARDING section of
 * docs/agencx/design/prototypes/agencx-prototype-v6.html: a full-bleed thread
 * that IS the screen - no title, no nav, and no progress surface of any kind
 * (design/frontend.md section 9: "the thread is the progress indicator"). The
 * composer renders whatever widget the server's InputSpec asks for
 * (BeatComposer); confirm is server-gated via ``can_confirm`` rather than a
 * client-side draft-length guess.
 *
 * The captured profile is shown back on the Business tab (S2), not here.
 */
export default function OnboardingPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [opening, setOpening] = useState<string | null>(null);
  const [completed, setCompleted] = useState(false);
  const [stage, setStage] = useState("");
  const [input, setInput] = useState<InputSpec | null>(null);
  const [canConfirm, setCanConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [openingPaced, setOpeningPaced] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  function applyStateFields(fields: StateFields) {
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
          // A returning owner sees the whole thread at once - never re-paced.
          setMessages(restored);
          setOpeningPaced(true);
        } else if (!state.completed) {
          setOpening(state.prompt);
        }
      })
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Failed to load onboarding"))
      .finally(() => setLoaded(true));
  }, []);

  // Hold the typing indicator ahead of the (static) opening message.
  useEffect(() => {
    if (!opening || openingPaced) return;
    const timer = setTimeout(() => setOpeningPaced(true), OPENING_PACE_MS);
    return () => clearTimeout(timer);
  }, [opening, openingPaced]);

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
              break; // the typing indicator is already up - nothing to change
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

  // The veil lifts for good once the owner has answered once (prototype
  // `#phone.started`).
  const started = messages.some((message) => message.role === "customer");
  // Never let the opening message still be "typing" once the conversation has
  // moved past it - a fast answer would otherwise pop the lede in AFTER the
  // reply it precedes.
  const openingShown = openingPaced || messages.length > 0;

  if (!loaded) {
    return (
      <main className="flex flex-1 items-center justify-center bg-surface p-8">
        <div aria-busy="true" className="h-8 w-8 animate-pulse rounded-full bg-surface-container" />
      </main>
    );
  }

  return (
    <main className="relative flex h-dvh min-h-0 flex-col overflow-hidden bg-surface">
      <ThreadVeil started={started} />

      <Thread
        label="Onboarding conversation"
        watch={messages}
        data-testid="onboarding-thread"
      >
        {completed ? (
          <AgentLine>You are live. Your assistant is answering for you now.</AgentLine>
        ) : (
          <>
            {opening ? (
              openingShown ? (
                <LedeMessage>{opening}</LedeMessage>
              ) : (
                <TypingLine />
              )
            ) : null}
            {messages.map((message, index) =>
              message.role === "customer" ? (
                <OwnerBubble key={index}>{message.text}</OwnerBubble>
              ) : message.streaming && !message.text ? (
                <TypingLine key={index} />
              ) : (
                <AgentLine key={index} streaming={message.streaming ?? false}>
                  {message.text}
                </AgentLine>
              ),
            )}
          </>
        )}
      </Thread>

      <div className="relative z-[1] shrink-0 px-gutter pb-[max(12px,env(safe-area-inset-bottom))] pt-3">
        <div className="mx-auto w-full max-w-thread">
          {!completed && canConfirm ? (
            <Button onClick={handleConfirm} loading={busy} data-testid="onboarding-confirm">
              Confirm and go live
            </Button>
          ) : !completed && input ? (
            <BeatComposer
              key={stage}
              input={input}
              busy={busy}
              onText={(text) => void sendText(text)}
              onSelect={(values) => void sendSelection(values)}
              onStop={handleStop}
            />
          ) : null}

          {/* Mounted unconditionally (only the text toggles) - screen readers
              reliably announce changes inside an existing live region, but
              often miss one that appears and disappears. Sits outside the
              thread's role="log" so the two never compete. */}
          <p
            role="status"
            data-testid={error ? "onboarding-error" : undefined}
            className="mt-2 h-4 text-meta text-text-secondary"
          >
            {error ?? (busy ? "Answering…" : "")}
          </p>
        </div>
      </div>
    </main>
  );
}
