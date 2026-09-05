"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import {
  AgentLine,
  LedeMessage,
  OwnerBubble,
  ProcessingLine,
  Thread,
  ThreadPill,
  ThreadVeil,
  TypingLine,
} from "@/components/ui/Thread";
import { ThinkingDots } from "@/components/ui/ThinkingDots";
import { useAuth } from "@/components/AuthProvider";
import { apiFetch, apiFetchStream, ApiError } from "@/lib/api";
import {
  describeUpload,
  foldReply,
  parseOnboardingEvent,
  type InputSpec,
  type OnboardingDraft,
  type OnboardingState,
} from "@/lib/onboarding";
import { BeatComposer } from "./components/BeatComposer";
import {
  type KnowledgeRecord,
  type PendingOffering,
  type ReviewOffering,
} from "@/components/knowledge/types";
import { ReviewSheet } from "@/components/knowledge/ReviewSheet";

interface Message {
  /** Set only for messages updated after they are pushed (upload stamps). */
  id?: string;
  role: "assistant" | "customer" | "stamp";
  text: string;
  streaming?: boolean;
  /** W-3: a "stamp" message mid-upload - renders animated dots beside it. */
  pending?: boolean;
}

/** A state snapshot without history[] - the SSE ``state`` event carries these. */
interface StateFields {
  stage: string;
  draft: OnboardingDraft;
  completed: boolean;
  input: InputSpec | null;
  can_confirm: boolean;
  suggested_slug: string | null;
  paused_beat: string | null;
  offering_candidates?: PendingOffering[];
}

/**
 * The prototype's `agentMsg()` holds the typing indicator before a message even
 * when that message is static, so pacing reads the same from the first beat
 * (design/frontend.md section 9). Only the opening message of a fresh
 * conversation is paced - restored history renders at once, per the S1 spec's
 * drop-off/return row.
 */
const OPENING_PACE_MS = 820;

/**
 * E-1 US-3: after completion the owner lands on /home. The confirm keeps the
 * "You are live" line readable for this long before the app appears, so go-live
 * reads as one conversation that became an app rather than a hard cut.
 *
 * O-8: this used to be 1400ms spent on an *empty* screen - the thread was
 * replaced by that single line, so the pause read as a stall rather than as a
 * beat. The line is now appended to the conversation the owner has been having,
 * nothing is unmounted, and /home is prefetched the moment confirming becomes
 * possible. With no blank frame to sit through, a shorter hold is enough.
 */
const GO_LIVE_READ_MS = 700;

/** The activation line. Appended to the thread, so it is the assistant's last
 *  word in the conversation rather than a screen of its own. */
const GO_LIVE_LINE =
  "You are live. Your customers get answers now, day or night.";

/**
 * The prototype's `.proc-txt` line while a pasted link is being fetched. The
 * backend leads its URL turn with `progress: reading_site` precisely so this
 * covers the scrape, the ingest and the extraction.
 */
const PROCESSING_COPY: Record<string, string> = {
  reading_site: "Reading your site\u2026",
};

/**
 * W-3: the recovery line every upload failure ends with, whether or not the
 * server gave a reason - it always names the way through, the "+" the file
 * came in from.
 */
const UPLOAD_RECOVERY =
  "Try again with the +, or tell me about it in a sentence.";

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
  const router = useRouter();
  // O-6: the address O-2 captured at login, offered as a one-tap chip on the
  // contact beat. Only the client holds it - it lives in Supabase auth, not in
  // the `users` table the API can read.
  const { user } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [opening, setOpening] = useState<string | null>(null);
  const [completed, setCompleted] = useState(false);
  const [stage, setStage] = useState("");
  const [input, setInput] = useState<InputSpec | null>(null);
  const [canConfirm, setCanConfirm] = useState(false);
  const [pausedBeat, setPausedBeat] = useState<string | null>(null);
  const [publicSlug, setPublicSlug] = useState("");
  // W-7: the go-live screen confirms only the address. The business name is
  // read back for reassurance (not editable - it was captured during the
  // interview), so the page holds the value but no input state for it.
  const [businessName, setBusinessName] = useState("");
  const [busy, setBusy] = useState(false);
  const [processing, setProcessing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [ownerOfferings, setOwnerOfferings] = useState<PendingOffering[]>([]);
  const [drafts, setDrafts] = useState<KnowledgeRecord[]>([]);
  const [reviewing, setReviewing] = useState<KnowledgeRecord | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [openingPaced, setOpeningPaced] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const goLiveTimer = useRef<number | null>(null);

  function applyStateFields(fields: StateFields) {
    setCompleted(fields.completed);
    setStage(fields.stage);
    setInput(fields.input);
    setCanConfirm(fields.can_confirm);
    setPausedBeat(fields.paused_beat);
    setOwnerOfferings(fields.offering_candidates ?? []);
    setBusinessName((current) => current || fields.draft.business_name || "");
    // W-7/W-4 US-1: prefill the address as soon as there is a real suggestion
    // (business name captured) or the confirm step is reached, on every path -
    // the upload -> review -> save path flips can_confirm from its own handler
    // and used to bypass this. Gating on a non-empty suggestion is what avoids
    // locking the reserved-name fallback ("business" -> "business-page") from an
    // early event before the name exists. `current || ...` never overwrites
    // what the owner has typed.
    if (fields.suggested_slug || fields.can_confirm) {
      setPublicSlug((current) => current || fields.suggested_slug || "business");
    }
  }

  useEffect(() => {
    Promise.all([
      apiFetch<OnboardingState>("/api/onboarding/state"),
      apiFetch<KnowledgeRecord[]>("/api/knowledge/records"),
    ])
      .then(([state, records]) => {
        // E-1: a business that is already live has no interview left to run -
        // it belongs in the app. The in-session confirm still finishes here,
        // so the owner reads "you are live" before the next visit redirects.
        if (state.completed) {
          router.replace("/home");
          return;
        }
        applyStateFields(state);
        const pending = records.filter((record) => record.status === "draft");
        setDrafts(pending);
        if (pending[0]) {
          setCanConfirm(false);
          setReviewing(withCombinedOfferings(pending[0], state.offering_candidates ?? []));
        }
        const restored = historyToMessages(state.history);
        if (restored.length > 0) {
          // A returning owner sees the whole thread at once - never re-paced.
          setMessages(restored);
          setOpeningPaced(true);
        } else if (!state.completed) {
          setOpening(state.prompt);
        }
      })
      .catch((err) =>
        setError(
          err instanceof ApiError ? err.detail : "Failed to load onboarding",
        ),
      )
      .finally(() => setLoaded(true));
  }, [router]);

  /**
   * O-8: warm /home the moment the interview is finishable. The route pulls its
   * own brief from three endpoints on mount, so an unprefetched navigation puts
   * that cold work between the confirm and the first painted frame - which is
   * the part that read as a lag.
   */
  useEffect(() => {
    if (canConfirm) router.prefetch("/home");
  }, [canConfirm, router]);

  // Never leave a navigation queued against an unmounted page.
  useEffect(
    () => () => {
      if (goLiveTimer.current !== null)
        window.clearTimeout(goLiveTimer.current);
    },
    [],
  );

  // Hold the typing indicator ahead of the (static) opening message.
  useEffect(() => {
    if (!opening || openingPaced) return;
    const timer = setTimeout(() => setOpeningPaced(true), OPENING_PACE_MS);
    return () => clearTimeout(timer);
  }, [opening, openingPaced]);

  function updateById(id: string, update: Partial<Message>) {
    setMessages((prev) =>
      prev.map((message) =>
        message.id === id ? { ...message, ...update } : message,
      ),
    );
  }

  function updateLastAssistant(update: (last: Message) => Partial<Message>) {
    setMessages((prev) => {
      const next = [...prev];
      const last = next[next.length - 1];
      if (last && last.role === "assistant")
        next[next.length - 1] = { ...last, ...update(last) };
      return next;
    });
  }

  async function sendText(text: string) {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    setError(null);
    setBusy(true);
    setProcessing(null);
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
              // Named work replaces the dots; anything unnamed leaves them up.
              setProcessing(PROCESSING_COPY[event.stage] ?? null);
              break;
            case "token":
            case "redraft":
            case "reply":
              setProcessing(null);
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
      const records = await apiFetch<KnowledgeRecord[]>("/api/knowledge/records");
      const pending = records.filter((record) => record.status === "draft");
      setDrafts(pending);
      if (pending[0]) {
        setCanConfirm(false);
        setReviewing(withCombinedOfferings(pending[0], ownerOfferings));
      }
    } catch (err) {
      // W-3: an aborted stream and a failed request both leave no reply behind
      // - either way, drop the empty placeholder bubble (or mark it settled if
      // some text already arrived) rather than leaving it "streaming" forever.
      // A failed request used to skip this, so its TypingLine stuck around
      // after busy cleared - two pending indicators disagreeing about whether
      // the turn was still in flight.
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last && last.role === "assistant" && last.text === "")
          return prev.slice(0, -1);
        const next = [...prev];
        if (last) next[next.length - 1] = { ...last, streaming: false };
        return next;
      });
      if (!(err instanceof Error && err.name === "AbortError")) {
        setError(err instanceof ApiError ? err.detail : "Something went wrong");
      }
    } finally {
      abortRef.current = null;
      setProcessing(null);
      setBusy(false);
    }
  }

  async function sendSelection(values: string[], label: string) {
    if (busy) return;
    setError(null);
    setBusy(true);
    setMessages((prev) => [
      ...prev,
      { role: "customer", text: label },
      { role: "assistant", text: "", streaming: true },
    ]);
    try {
      const state = await apiFetch<OnboardingState>("/api/onboarding/message", {
        method: "POST",
        body: JSON.stringify({ selection: { beat: stage, values } }),
      });
      applyStateFields(state);
      setMessages(historyToMessages(state.history));
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        try {
          const state = await apiFetch<OnboardingState>("/api/onboarding/state");
          applyStateFields(state);
          setMessages(historyToMessages(state.history));
          setError("Setup refreshed. Choose your answer again.");
        } catch {
          setError("Setup changed. Refresh the page and try again.");
        }
      } else {
        setMessages((prev) => prev.slice(0, -2));
        setError(err instanceof ApiError ? err.detail : "Something went wrong");
      }
    } finally {
      setBusy(false);
    }
  }

  async function resumePausedBeat() {
    if (busy) return;
    setError(null);
    setBusy(true);
    try {
      const state = await apiFetch<OnboardingState>("/api/onboarding/message", {
        method: "POST",
        body: JSON.stringify({ resume: true }),
      });
      applyStateFields(state);
      setMessages(historyToMessages(state.history));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  /**
   * Files attached through the pill's "+". Each file gets its own stamp and its
   * own line, uploaded one at a time so the thread reads in order. Knowledge is
   * never a blocking beat: a refused or failed file leaves one calm line and the
   * interview carries on.
   *
   * ponytail: the stamps are client-side only - the ingested document is
   * persisted, its stamp is not, so a reload shows the thread without them.
   * Persisting them needs an onboarding-side record of the attachment.
   */
  async function uploadFiles(files: File[]) {
    if (busy) return;
    setError(null);
    setBusy(true);
    const accepted: KnowledgeRecord[] = [];
    try {
      for (const file of files) {
        const verdict = describeUpload(file.name);
        if (!verdict.accepted) {
          setMessages((prev) => [
            ...prev,
            { role: "assistant", text: verdict.message },
          ]);
          continue;
        }
        const id = crypto.randomUUID();
        // W-3: the stamp itself carries the animated processing state
        // (ThinkingDots, rendered beside `message.text` in the thread) instead
        // of a frozen "adding\u2026" suffix - reading and scrolling stay available
        // while extraction runs, and `pending` is always resolved explicitly
        // below, on both the success and the failure path.
        setMessages((prev) => [
          ...prev,
          { id, role: "stamp", text: file.name, pending: true },
        ]);
        const form = new FormData();
        form.append("file", file);
        form.append("doc_type", "other");
        try {
          const draft = await apiFetch<KnowledgeRecord>("/api/knowledge/drafts/upload", {
            method: "POST",
            body: form,
          });
          setCanConfirm(false);
          accepted.push(draft);
          setDrafts((previous) => [...previous, draft]);
          updateById(id, { text: `${file.name} \u00b7 added`, pending: false });
          setMessages((prev) => [
            ...prev,
            { role: "assistant", text: `I found ${file.name}. Review it before it answers customers.` },
          ]);
        } catch (err) {
          updateById(id, { text: `${file.name} \u00b7 not added`, pending: false });
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              text:
                err instanceof ApiError && err.detail
                  ? `I couldn't read that one. ${err.detail} ${UPLOAD_RECOVERY}`
                  : `I couldn't read that one. ${UPLOAD_RECOVERY}`,
            },
          ]);
        }
      }
      if (accepted[0]) setReviewing(withCombinedOfferings(accepted[0], ownerOfferings));
    } finally {
      setBusy(false);
    }
  }

  function nextDraft(excluding: string): KnowledgeRecord | null {
    return drafts.find((draft) => draft.id !== excluding) ?? null;
  }

  async function saveKnowledge(
    sections: { heading: string; body: string }[],
    offerings: PendingOffering[],
  ) {
    if (!reviewing) return;
    setReviewError(null);
    setBusy(true);
    try {
      const response = await apiFetch<{
        record: KnowledgeRecord;
        offering_candidates: PendingOffering[];
      }>(`/api/onboarding/knowledge/${reviewing.id}`, {
        method: "PUT",
        body: JSON.stringify({ sections, offerings }),
      });
      const remaining = nextDraft(reviewing.id);
      setOwnerOfferings(response.offering_candidates);
      setDrafts((previous) => previous.filter((draft) => draft.id !== reviewing.id));
      setReviewing(remaining ? withCombinedOfferings(remaining, response.offering_candidates) : null);
      setCanConfirm(!remaining);
    } catch (err) {
      setReviewError(err instanceof ApiError ? err.detail : "I couldn't save that information.");
    } finally {
      setBusy(false);
    }
  }

  async function discardKnowledge() {
    if (!reviewing) return;
    setReviewError(null);
    setBusy(true);
    try {
      await apiFetch(`/api/knowledge/records/${reviewing.id}`, { method: "DELETE" });
      const remaining = nextDraft(reviewing.id);
      setDrafts((previous) => previous.filter((draft) => draft.id !== reviewing.id));
      setReviewing(remaining ? withCombinedOfferings(remaining, ownerOfferings) : null);
      setCanConfirm(!remaining);
    } catch (err) {
      setReviewError(err instanceof ApiError ? err.detail : "I couldn't discard that draft.");
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
      await apiFetch("/api/onboarding/confirm", {
        method: "POST",
        body: JSON.stringify({ slug: publicSlug }),
      });
      setCompleted(true);
      setCanConfirm(false);
      setInput(null);
      // The payoff line joins the conversation instead of replacing it.
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: GO_LIVE_LINE },
      ]);
      goLiveTimer.current = window.setTimeout(
        () => router.replace("/home"),
        GO_LIVE_READ_MS,
      );
      // Deliberately no setBusy(false): the button stays held until the route
      // changes. Releasing it re-armed a second click, and the second confirm
      // 409s "already confirmed" - painting an error over the live line.
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.detail
          : "Something went wrong. Please try again.",
      );
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
        <div
          aria-busy="true"
          className="h-8 w-8 animate-pulse rounded-full bg-surface-container"
        />
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
          ) : message.role === "stamp" ? (
            <ThreadPill key={index}>
              {message.text}
              {/* W-3: the animated processing state for this stamp - aria-hidden
                  and no live region of its own, so it does not collide with the
                  thread's own role="log" (Thread.tsx:55-57). */}
              {message.pending ? <ThinkingDots className="ml-2" /> : null}
            </ThreadPill>
          ) : message.streaming && !message.text ? (
            processing ? (
              <ProcessingLine key={index}>{processing}</ProcessingLine>
            ) : (
              <TypingLine key={index} />
            )
          ) : (
            <AgentLine key={index} streaming={message.streaming ?? false}>
              {message.text}
            </AgentLine>
          ),
        )}
      </Thread>

      <div className="relative z-[1] shrink-0 px-gutter pb-[max(12px,env(safe-area-inset-bottom))] pt-3">
        <div className="mx-auto w-full max-w-thread">
          {!completed && canConfirm && !reviewing ? (
            <div className="flex flex-col gap-3">
              {businessName ? (
                <p className="text-meta text-ink-a40" data-testid="onboarding-going-live-as">
                  Going live as {businessName}.
                </p>
              ) : null}
              <Input
                label="Your business page"
                value={publicSlug}
                onChange={(event) => setPublicSlug(event.target.value.toLowerCase())}
                help={`Shared as agencx.app/${publicSlug}`}
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
                disabled={busy}
                data-testid="onboarding-public-slug"
              />
              <Button
                onClick={handleConfirm}
                loading={busy}
                data-testid="onboarding-confirm"
              >
                Confirm and go live
              </Button>
            </div>
          ) : !completed && pausedBeat ? (
            <div className="flex flex-col gap-2" data-testid="onboarding-paused">
              <p className="text-meta text-ink-a40">
                Finish this field when you are ready to keep setting up your assistant.
              </p>
              <Button onClick={() => void resumePausedBeat()} loading={busy}>
                Try again
              </Button>
            </div>
          ) : !completed && input ? (
            <BeatComposer
              key={stage}
              input={input}
              busy={busy}
              onText={(text) => void sendText(text)}
              onSelection={(values, label) => void sendSelection(values, label)}
              onStop={handleStop}
              ownerEmail={user?.email ?? null}
              onFiles={(files) => void uploadFiles(files)}
            />
          ) : null}

          {/* Mounted unconditionally (only the text toggles) - screen readers
              reliably announce changes inside an existing live region, but
              often miss one that appears and disappears. Sits outside the
              thread's role="log" so the two never compete. */}
          {/* W-3: TypingLine in the thread is the sole pending-turn indicator
              now - this slot holds nothing while a turn is in flight, and
              carries only the error text. */}
          <p
            role="status"
            data-testid={error ? "onboarding-error" : undefined}
            className={`mt-2 h-4 text-meta ${error ? "text-danger" : "text-text-secondary"}`}
          >
            {error ?? ""}
          </p>
        </div>
      </div>
      <ReviewSheet
        record={reviewing}
        busy={busy}
        priceConflict={reviewError}
        onboarding
        onClose={() => {
          setReviewError(null);
          setReviewing(null);
        }}
        onSave={(sections, offerings) => void saveKnowledge(sections, offerings)}
        onDiscard={() => void discardKnowledge()}
      />
    </main>
  );
}

function withCombinedOfferings(
  record: KnowledgeRecord,
  ownerOfferings: PendingOffering[],
): KnowledgeRecord {
  const merged = new Map<string, ReviewOffering>();
  for (const item of ownerOfferings) merged.set(normalizeOfferingName(item.name), { ...item });
  for (const item of record.offering_candidates ?? []) {
    const key = normalizeOfferingName(item.name);
    const owner = merged.get(key);
    if (!owner) {
      merged.set(key, { ...item, sources: ["document"] });
      continue;
    }
    const options = [owner.price_cents, item.price_cents].filter(
      (price): price is number => price !== null,
    );
    merged.set(key, {
      ...owner,
      description: owner.description || item.description,
      price_cents: owner.price_cents ?? item.price_cents,
      sources: [...new Set([...owner.sources, ...item.sources])],
      price_options: new Set(options).size > 1 ? [...new Set(options)] : undefined,
    });
  }
  return { ...record, offering_candidates: [...merged.values()] };
}

function normalizeOfferingName(value: string): string {
  return value
    .normalize("NFKC")
    .trim()
    .toLowerCase()
    .replace(/[\p{P}]/gu, " ")
    .replace(/\s+/g, " ");
}
