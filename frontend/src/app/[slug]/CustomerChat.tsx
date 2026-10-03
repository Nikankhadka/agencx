"use client";

import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
  type RefObject,
} from "react";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Input } from "@/components/ui/Input";
import { ChatBubble, type ChatRole } from "@/components/ui/ChatBubble";
import { Chip } from "@/components/ui/Chip";
import { StreamingText } from "@/components/ui/StreamingText";
import { CitationChip, type Citation } from "@/components/ui/CitationChip";
import { QuoteCard, type QuotePayload } from "@/components/ui/QuoteCard";
import { PriceSummaryCard, type PriceSummaryPayload } from "@/components/ui/PriceSummaryCard";
import { CatalogCard, type CatalogPayload } from "@/components/ui/CatalogCard";
import { EscalationBanner } from "@/components/ui/EscalationBanner";
import { parseChatStreamEvent, type ChatStreamEvent } from "@/lib/chat-events";
import { messageFromPublic } from "@/lib/chat-restore";
import type { PublicMessage } from "@/lib/api-schemas";
import { handoffRequestBody, shouldShowAskForPerson } from "@/lib/handoff";
import { customerOpening } from "@/lib/greeting";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// RF-10/RF-12: same-tab refresh keys. sessionStorage (not localStorage) is
// deliberate - this is continuity for one tab, not a durable identity. The
// conversation id lets a reload restore the transcript and cards; the name
// keeps the chip coherent before the fetch resolves; the draft and the two
// banner flags round out the state a refresh would otherwise drop. No owner-only
// value is ever stored here.
const conversationKey = (slug: string) => `agencx:chat:conversation:${slug}`;
const nameKey = (slug: string) => `agencx:chat:name:${slug}`;
const draftKey = (slug: string) => `agencx:chat:draft:${slug}`;
const handoffKey = (slug: string) => `agencx:chat:handoff:${slug}`;
const escalatedKey = (slug: string) => `agencx:chat:escalated:${slug}`;

function readSession(key: string): string | null {
  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeSession(key: string, value: string): void {
  try {
    window.sessionStorage.setItem(key, value);
  } catch {
    // Storage unavailable (private mode, quota): refresh restoration is a
    // nicety, never worth failing a turn or a render over.
  }
}

/**
 * Hydrate the chip name, conversation id, composer draft, and banner flags from
 * sessionStorage into React state, returning the stored id (or null). Kept a
 * module-level function rather than inlined in the effect for the same reason
 * `subscribeToMediaQuery` is: the effect then wires the external store instead
 * of directly setting state.
 */
function hydrateFromSession(
  slug: string,
  setName: (name: string) => void,
  setId: (id: string) => void,
  setDraft: (draft: string) => void,
  setHandoffSeen: (value: boolean) => void,
  setEscalated: (value: boolean) => void,
): string | null {
  const storedName = readSession(nameKey(slug));
  if (storedName) setName(storedName);
  const storedId = readSession(conversationKey(slug));
  if (storedId) setId(storedId);
  const storedDraft = readSession(draftKey(slug));
  if (storedDraft) setDraft(storedDraft);
  if (readSession(handoffKey(slug)) === "1") setHandoffSeen(true);
  if (readSession(escalatedKey(slug)) === "1") setEscalated(true);
  return storedId;
}

interface Message {
  role: ChatRole;
  text: string;
  citations?: Citation[];
  quote?: QuotePayload;
  priceSummary?: PriceSummaryPayload;
  catalog?: CatalogPayload;
  streaming?: boolean;
  error?: boolean;
  /**
   * RF-13: the exact customer payload that this failed assistant bubble tried
   * to answer. Retry replays this verbatim, so the button never reads a
   * neighboring bubble. Absent on a healthy turn and on a handoff failure,
   * which has no customer payload to replay.
   */
  retryText?: string;
}

const POLL_INTERVAL_MS = 5000;

function renderWithCitations(text: string, citations: Citation[]): ReactNode {
  const parts = text.split(/(\[\d+\])/g);
  return parts.map((part, i) => {
    const match = part.match(/^\[(\d+)\]$/);
    const citation = match ? citations.find((c) => c.index === Number(match[1])) : undefined;
    return citation ? <CitationChip key={i} citation={citation} /> : <span key={i}>{part}</span>;
  });
}

/**
 * T-011/T-032: the interactive half of the customer surface. The branded
 * shell/suspended/not-found states stay in page.tsx (server-resolved, T-005)
 * - this component owns the actual conversation once the shell has decided
 * the tenant is active. No EventSource (POST bodies aren't supported by
 * it) - SSE is parsed by hand from a fetch ReadableStream.
 */
export function CustomerChat({
  slug,
  displayName,
  greeting,
  starterQuestions,
  composerRef,
}: {
  slug: string;
  displayName: string;
  greeting: string | null;
  starterQuestions: string[];
  /** Filled with a function that puts text in the composer, for a parent whose
   * own buttons open this chat with a question already typed. Seeding is an
   * event, so it is a call rather than a prop: a prop would have to be turned
   * back into one, and the obvious way to do that - remounting on a new value
   * - is exactly what throws away the conversation it was opened from. */
  composerRef?: RefObject<((text: string) => void) | null>;
}) {
  // W-9 US-8: the assistant says what it is first, in words the tenant does not
  // own. A configured welcome follows it, minus anything that would say hello a
  // second time.
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", text: customerOpening(displayName, greeting) },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  // RF-10: the customer's preferred display name, shown in a small chip. Null
  // until a `contact` event or a sessionStorage restore supplies one.
  const [customerName, setCustomerName] = useState<string | null>(null);
  // C-5 split one flag in two. `escalated` means a tenant limit ended the
  // conversation - the only case that locks the composer. `handoffSeen` means
  // the assistant asked a human to look at something, which is a notification,
  // not a stop: the chat stays live and only the human-reply poll starts.
  const [escalated, setEscalated] = useState(false);
  const [handoffSeen, setHandoffSeen] = useState(false);
  // Starter chips only make sense before the customer has said anything -
  // hidden the moment the first real message goes out, never shown again.
  const [showStarters, setShowStarters] = useState(starterQuestions.length > 0);
  // Cursor for the transcript poll: the created_at of the newest message we
  // have already fetched. Starts undefined so the first poll fetches the whole
  // tail once, then narrows each tick.
  const pollCursor = useRef<string | undefined>(undefined);

  useEffect(() => {
    if (!composerRef) return;
    composerRef.current = (text: string) => {
      setInput(text);
      // RF-12: a seeded question is still an unsent draft, so it persists too.
      writeSession(draftKey(slug), text);
    };
    return () => {
      composerRef.current = null;
    };
  }, [composerRef, slug]);

  // RF-10/RF-12: same-tab refresh. Restore the stored name (so the chip is
  // coherent before the fetch resolves), composer draft, and banner flags, and
  // when a conversation id was stored, the text transcript (with each turn's
  // restored card) via the existing public messages endpoint. A failed restore
  // falls back to the opening state.
  useEffect(() => {
    const storedId = hydrateFromSession(
      slug,
      setCustomerName,
      setConversationId,
      setInput,
      setHandoffSeen,
      setEscalated,
    );
    if (!storedId) return;
    let cancelled = false;
    void (async () => {
      try {
        const params = new URLSearchParams({ slug });
        const res = await fetch(
          `${API_URL}/api/chat/${storedId}/messages?${params.toString()}`,
        );
        if (!res.ok || cancelled) return;
        const incoming = (await res.json()) as PublicMessage[];
        if (cancelled || incoming.length === 0) return;
        setMessages(incoming.map<Message>((m) => messageFromPublic(m)));
        setShowStarters(false);
      } catch {
        // Transient or unexpected: keep the opening state rather than block.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [slug]);

  // T-031/C-5: once a topic has been handed to a human, that human may reply
  // (the escalations resolve flow inserts a human_agent message). No push
  // channel exists, so poll the public transcript endpoint and append what
  // arrives. Polling starts on a handoff or a limit stop and runs until
  // unmount; it never runs on a tab that has neither, which keeps it off the
  // backend's back.
  useEffect(() => {
    if (!(handoffSeen || escalated) || !conversationId) return;

    let cancelled = false;

    async function poll() {
      const params = new URLSearchParams({ slug });
      if (pollCursor.current) params.set("after", pollCursor.current);
      try {
        const res = await fetch(
          `${API_URL}/api/chat/${conversationId}/messages?${params.toString()}`
        );
        if (!res.ok || cancelled) return;
        const incoming = (await res.json()) as PublicMessage[];
        if (cancelled || incoming.length === 0) return;
        pollCursor.current = incoming[incoming.length - 1]?.created_at ?? pollCursor.current;
        // Only a human's reply. C-5 keeps the conversation open, so the
        // customer's own messages and the assistant's answers keep being
        // persisted while this poll runs - taking everything would render each
        // of them a second time. A human reply is the one thing this client
        // cannot learn about any other way, and it is all the poll is for.
        const replies = incoming.filter((m) => m.role === "human_agent");
        if (replies.length === 0) return;
        setMessages((prev) => {
          // Dedupe by role + content (the transcript carries no ids the
          // streamed messages share). Applied on every tick, not just the
          // first: a page that restored history already shows earlier replies,
          // and two identical human replies in one thread are far less likely
          // than the double-render this prevents.
          const shown = new Set(prev.map((m) => `${m.role}\0${m.text}`));
          const additions = replies
            .filter((m) => !shown.has(`${m.role}\0${m.content}`))
            .map<Message>((m) => ({ role: m.role as ChatRole, text: m.content }));
          return additions.length > 0 ? [...prev, ...additions] : prev;
        });
      } catch {
        // Transient network error - the next tick retries.
      }
    }

    void poll();
    const timer = setInterval(() => void poll(), POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [handoffSeen, escalated, conversationId, slug]);

  /**
   * RF-13: update one assistant bubble by index. A fresh send and a retry both
   * target the assistant bubble they created, so a stream event lands on the
   * right turn even though the array may have grown since the request started
   * (a polled human reply, another turn). Index rather than "last" is what lets
   * retry reinstate the failed bubble in place instead of appending.
   */
  function updateAssistantAt(index: number, update: (message: Message) => Partial<Message>) {
    setMessages((prev) => {
      const target = prev[index];
      if (!target) return prev;
      const next = [...prev];
      next[index] = { ...target, ...update(target) };
      return next;
    });
  }

  /**
   * RF-13: the shared failure path. It stamps the failed bubble with the retry
   * affordance and the exact payload, and puts that payload back in the
   * composer while keeping the stored draft. A handoff failure passes no
   * payload and only gets the bubble, since there is nothing to replay.
   */
  function failTurn(index: number, retryText: string | undefined) {
    updateAssistantAt(index, () => ({
      text: "Something went wrong just then. Try again?",
      error: true,
      streaming: false,
      retryText,
    }));
    if (retryText !== undefined) {
      setInput(retryText);
      writeSession(draftKey(slug), retryText);
    }
  }

  /**
   * RF-13: one attempt at a turn against the live stream, shared by a fresh
   * send and an explicit retry. The target assistant bubble already exists at
   * `index`; a failure stamps the payload onto it for a later retry.
   */
  async function runTurn(index: number, text: string) {
    try {
      const res = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slug, conversation_id: conversationId, message: text }),
      });
      if (!res.ok || !res.body) throw new Error("chat request failed");
      await consumeStream(res.body, index, text);
    } catch {
      failTurn(index, text);
    }
  }

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || busy || escalated) return;
    setBusy(true);
    // RF-13: the composer clears for normal typing feedback, but the exact
    // payload is held as the in-flight draft so a mid-flight refresh keeps it.
    // It is cleared only when the turn succeeds (the `done` handler).
    setInput("");
    writeSession(draftKey(slug), trimmed);
    setShowStarters(false);
    // The assistant placeholder this turn owns: one past the appended customer
    // bubble. The single in-flight-turn guard keeps this index stable.
    const assistantIndex = messages.length + 1;
    setMessages((prev) => [
      ...prev,
      { role: "customer", text: trimmed },
      { role: "assistant", text: "", streaming: true },
    ]);

    try {
      await runTurn(assistantIndex, trimmed);
    } finally {
      setBusy(false);
    }
  }

  // RF-13: the explicit retry, the only thing that replays a failed send -
  // there is no automatic loop. It reuses the failed bubble in place (no second
  // customer bubble) and posts the stored payload verbatim.
  async function retry(assistantIndex: number) {
    if (busy || escalated) return;
    const text = messages[assistantIndex]?.retryText;
    if (!text) return;
    setBusy(true);
    setInput("");
    writeSession(draftKey(slug), text);
    // Reinstate the bubble to streaming: drop the error state and the stale
    // payload, so a second failure stamps it again and a success leaves none.
    updateAssistantAt(assistantIndex, () => ({
      text: "",
      error: false,
      streaming: true,
      retryText: undefined,
    }));
    try {
      await runTurn(assistantIndex, text);
    } finally {
      setBusy(false);
    }
  }

  // RF-11: the deterministic handoff. It posts no message and runs no agent
  // turn - the backend records the escalation and streams the same handoff
  // reply the assistant's tool would. Busy-guarded like `send`, and hidden
  // once `handoffSeen` so it cannot be fired twice.
  async function askForPerson() {
    if (busy || !shouldShowAskForPerson({ escalated, handoffSeen })) return;
    setBusy(true);
    setShowStarters(false);
    const assistantIndex = messages.length;
    setMessages((prev) => [...prev, { role: "assistant", text: "", streaming: true }]);

    try {
      const res = await fetch(`${API_URL}/api/chat/handoff`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(handoffRequestBody(slug, conversationId)),
      });
      if (!res.ok || !res.body) throw new Error("handoff request failed");
      await consumeStream(res.body, assistantIndex, undefined);
      // An already-open escalation streams no reply, so drop the empty
      // placeholder rather than leave a blank assistant bubble.
      setMessages((prev) => {
        const target = prev[assistantIndex];
        if (target && target.role === "assistant" && target.text === "" && !target.error) {
          return prev.filter((_, i) => i !== assistantIndex);
        }
        return prev;
      });
    } catch {
      // A handoff failure has no customer payload, so it gets the bubble with
      // no retry control (there is nothing for the control to replay).
      failTurn(assistantIndex, undefined);
    } finally {
      setBusy(false);
    }
  }

  async function consumeStream(
    body: ReadableStream<Uint8Array>,
    targetIndex: number,
    retryText: string | undefined,
  ) {
    const reader = body.getReader();
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
        // A malformed or partial SSE frame parses to null; skip it and keep
        // reading rather than abort the in-progress stream.
        const event = parseChatStreamEvent(raw.slice("data: ".length));
        if (!event) continue;
        handleStreamEvent(event, targetIndex, retryText);
      }
    }
  }

  function handleStreamEvent(
    event: ChatStreamEvent,
    targetIndex: number,
    retryText: string | undefined,
  ) {
    switch (event.type) {
      case "conversation":
        setConversationId(event.conversation_id);
        // RF-10: one conversation per tab; without this a refresh loses
        // the thread entirely.
        writeSession(conversationKey(slug), event.conversation_id);
        break;
      case "citations":
        updateAssistantAt(targetIndex, () => ({ citations: event.citations }));
        break;
      case "contact":
        // RF-10: the preferred display name. Name only - never an email.
        if (event.name) {
          setCustomerName(event.name);
          writeSession(nameKey(slug), event.name);
        }
        break;
      case "quote":
        updateAssistantAt(targetIndex, () => ({ quote: event.quote }));
        break;
      case "price_summary":
        updateAssistantAt(targetIndex, () => ({ priceSummary: event.summary }));
        break;
      case "catalog":
        updateAssistantAt(targetIndex, () => ({ catalog: event.catalog }));
        break;
      case "progress":
        // The in-bubble typing indicator already covers the wait; no
        // separate status line to update.
        break;
      case "redraft":
        // The backend's price gate rejected the streamed draft and is
        // streaming a replacement - clear the rejected text.
        updateAssistantAt(targetIndex, () => ({ text: "" }));
        break;
      case "token":
        updateAssistantAt(targetIndex, (target) => ({ text: target.text + event.text }));
        break;
      case "refusal":
        updateAssistantAt(targetIndex, () => ({ text: event.text }));
        break;
      case "handoff":
        // A human was notified. Nothing about the chat changes.
        setHandoffSeen(true);
        // RF-12: persist it so a refresh keeps the human-reply poll running and
        // the "Ask for a person" control hidden.
        writeSession(handoffKey(slug), "1");
        break;
      case "escalated":
        setEscalated(true);
        // RF-12: a limit stop is terminal; a refresh must restore the locked
        // composer and the banner, not reopen the chat.
        writeSession(escalatedKey(slug), "1");
        break;
      case "error":
        // The backend failed mid-stream and said so on the wire. Without
        // this the bubble would sit in "streaming" forever - show the same
        // retry affordance a network failure gets, carrying the exact payload.
        failTurn(targetIndex, retryText);
        break;
      case "done":
        updateAssistantAt(targetIndex, () => ({ streaming: false, retryText: undefined }));
        // RF-13: a completed turn clears the in-flight draft. A fresh send and
        // a retry both pass the customer payload, so only those clear the
        // composer; a handoff passes none and must not clobber a typed draft.
        if (retryText !== undefined) {
          setInput("");
          writeSession(draftKey(slug), "");
        }
        break;
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void send(input);
  }

  return (
    <>
      {customerName ? (
        // RF-10: display-only, so a span rather than a Button/Chip (which are
        // interactive). Prototype `.svc-lbl` recipe: text-chip type, chip radius,
        // accent wash, teal-m text. Name only, never an email.
        <span
          data-testid="customer-name-chip"
          className="mt-4 inline-flex w-fit items-center rounded-chip bg-accent-a07 px-3 py-1 text-chip font-medium text-info"
        >
          You&apos;re chatting as {customerName}
        </span>
      ) : null}
      <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto py-4">
        {messages.map((message, index) => (
          <ChatBubble key={index} role={message.role} senderLabel={`${displayName} staff`}>
            <StreamingText
              streaming={message.streaming ?? false}
              pending={message.streaming === true && message.text === ""}
            >
              {renderWithCitations(message.text, message.citations ?? [])}
            </StreamingText>
            {message.quote ? <QuoteCard quote={message.quote} /> : null}
            {message.priceSummary ? <PriceSummaryCard summary={message.priceSummary} /> : null}
            {message.catalog ? <CatalogCard catalog={message.catalog} /> : null}
            {message.error && message.retryText ? (
              <button
                type="button"
                data-testid="retry"
                onClick={() => void retry(index)}
                className="mt-1 block text-footnote font-medium text-accent-active transition-colors duration-(--duration-fast) hover:underline active:opacity-60"
              >
                Retry
              </button>
            ) : null}
          </ChatBubble>
        ))}
        {showStarters ? (
          <div className="flex flex-wrap gap-2 pl-1">
            {starterQuestions.map((question, index) => (
              <Chip
                key={index}
                label={question}
                dashed
                data-testid={`starter-${index}`}
                onClick={() => void send(question)}
              />
            ))}
          </div>
        ) : null}
      </div>

      {escalated ? (
        <EscalationBanner />
      ) : (
        <form
          onSubmit={handleSubmit}
          className="flex shrink-0 flex-col gap-2 border-t border-border pt-4 pb-[max(1rem,env(safe-area-inset-bottom))]"
        >
          {/* RF-11: the visible ask-for-a-person control. Ported from the
              prototype's `.thr-pill-action` idle-call idiom (a centered pill),
              kept in the composer so it is reachable at 360px and 1024px. */}
          {shouldShowAskForPerson({ escalated, handoffSeen }) ? (
            <div className="flex justify-center">
              <Chip
                label="Ask for a person"
                data-testid="ask-for-person"
                disabled={busy}
                onClick={() => void askForPerson()}
                className="disabled:opacity-50"
              />
            </div>
          ) : null}
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <Input
                label="Message"
                value={input}
                onChange={(e) => {
                  setInput(e.target.value);
                  // RF-12: persist the unsent draft so a refresh restores it.
                  writeSession(draftKey(slug), e.target.value);
                }}
                disabled={busy}
                autoFocus
              />
            </div>
            {/* No stop affordance: the customer never interrupts the
                assistant's own reply, so the send icon stays put rather than
                swapping to a control that would let them. */}
            <Button type="submit" disabled={busy} aria-label="Send">
              <Icon name="send" size={20} />
            </Button>
          </div>
        </form>
      )}
    </>
  );
}
