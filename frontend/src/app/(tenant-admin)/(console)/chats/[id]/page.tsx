"use client";

import { use, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "react-hot-toast";
import { Button } from "@/components/ui/Button";
import { ChatBubble } from "@/components/ui/ChatBubble";
import { CommandPill } from "@/components/ui/CommandPill";
import { ScreenTopbar } from "@/components/ui/ScreenTopbar";
import { Container } from "@/components/ui/Container";
import { Icon } from "@/components/ui/Icon";
import { StructuredResponse } from "@/components/ui/StructuredResponse";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { apiFetch, ApiError } from "@/lib/api";
import type { ConversationDetail } from "@/lib/api-schemas";
import { clockTime, customerLabel } from "@/lib/format";
import { invalidateConversationLists } from "../lib/useConversationQueue";

/**
 * C-6 Chats thread: the owner reads a conversation, steps into it, hands it
 * back, and resolves it.
 *
 * The states this screen exists to make obvious are "my assistant is handling
 * this", "I am replying", and "the ball is with the customer". All are named
 * in the topbar rather than implied by which controls are visible, because an
 * owner who is unsure which one is true will not type - and a message sent
 * while the assistant is still answering puts two voices in one thread.
 *
 * D44 adds resolution as an explicit action: any unresolved thread shows the
 * inline resolve shelf whether or not the owner has taken over. It takes its
 * own confirmation, closes any open escalation, and writes the owner-only
 * stamp; replying and handing back stay separate and never resolve anything.
 * A customer reply reopens the thread.
 *
 * Ported from agencx-prototype-v6.html's `renderThreadScreen` / `alexTko` /
 * `alexHbk`: `thr-st` status, the take-over and hand-back pills, and the
 * symmetrical stamps in the transcript. Mounted chrome-free until E-1.
 */

// The customer's own replies arrive while the owner is reading, and there is no
// push channel - same constraint, same answer, as the customer surface.
const POLL_INTERVAL_MS = 4000;

export default function ChatThreadPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  // Keyed remount: the desktop layout stays mounted across a route change, so
  // without this the reply draft, error, deleteError, and the RF-16 resolve
  // open/draft state would leak from one conversation to the next. Keying on
  // the id resets every hook by unmounting, rather than a reset-effect that
  // react-hooks/set-state-in-effect would reject.
  return <ChatThread key={id} id={id} />;
}

function ChatThread({ id }: { id: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Its own state, not `error`: the poll below clears `error` every 4s on a
  // successful load, which would wipe the reason a delete was refused.
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [working, setWorking] = useState(false);
  const [draft, setDraft] = useState("");
  // RF-16: the inline resolve shelf - its own draft, so a message typed for one
  // issue never carries over to the next, and its own open flag so a failed
  // submit leaves the text in place to retry.
  const [resolveOpen, setResolveOpen] = useState(false);
  const [resolveDraft, setResolveDraft] = useState("");
  const bottomRef = useRef<HTMLDivElement | null>(null);
  // RF-18: the conversation id whose read marker this mount has already sent,
  // so the 4s poll never re-sends it (and a route change to another id still
  // marks the new one).
  const readRequestedFor = useRef<string | null>(null);
  // Handing back ends the owner's voice in the thread - that asks first.
  // Stepping in never does: it only adds the owner, it takes nothing away.
  const { confirm, dialog: confirmDialog } = useConfirm();

  // Bumped after a takeover, handback or reply so the transcript refetches
  // immediately instead of waiting out the poll interval.
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const next = await apiFetch<ConversationDetail>(`/api/conversations/${id}`);
        if (cancelled) return;
        setDetail(next);
        setError(null);
        // RF-18: opening the thread marks it read, once. Invalidating the list
        // query means returning to /chats (and the tab badge) sees it read
        // instead of serving the cached unread summary.
        if (readRequestedFor.current !== id) {
          readRequestedFor.current = id;
          void apiFetch(`/api/conversations/${id}/read`, { method: "POST" })
            .then(() => invalidateConversationLists(queryClient))
            .catch(() => {
              if (readRequestedFor.current === id) readRequestedFor.current = null;
            });
        }
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.detail : "Could not load this conversation.");
      }
    }

    void load();
    const timer = setInterval(() => void load(), POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [id, reloadToken, queryClient]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [detail?.messages.length]);

  const takenOver = detail?.status === "human";
  // A conversation a tenant limit ended is not one to step into - the cap is
  // the point. The pill is simply absent rather than present-and-failing.
  const stopped = detail?.status === "escalated" || detail?.status === "closed";
  // D44: resolution is a lifecycle marker, not a status - the ownership axis
  // above is untouched. A resolved thread shows no controls until a customer
  // reply clears the marker.
  const resolved = detail?.resolved_at != null;
  const settled = stopped || resolved;
  // D43 on the thread: "waiting" means the owner's own reply was the last
  // word. The assistant's pre-takeover handoff must not displace C-6's
  // "You're replying" the moment an owner steps in - the queue row uses the
  // broader business-spoke-last predicate, and this is the one place the two
  // deliberately differ.
  const lastRole = [...(detail?.messages ?? [])].reverse().find((m) => m.role !== "system")?.role;
  const waitingOnCustomer = takenOver && lastRole === "human_agent";

  function statusLine(): string {
    if (resolved) return "Resolved";
    if (stopped) return "Stopped";
    if (waitingOnCustomer) return "Waiting on customer";
    if (takenOver) return "You're replying";
    return "Handling";
  }

  async function handleTakeover() {
    if (takenOver) {
      await confirm({
        title: "Hand this chat back?",
        description: "Your assistant resumes replying to this customer.",
        confirmLabel: "Hand back",
        onConfirm: () => act("handback"),
      });
    } else {
      void act("takeover");
    }
  }

  async function act(path: string, body?: unknown) {
    setWorking(true);
    setError(null);
    try {
      await apiFetch(`/api/conversations/${id}/${path}`, {
        method: "POST",
        ...(body ? { body: JSON.stringify(body) } : {}),
      });
      setReloadToken((token) => token + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "That didn't go through.");
    } finally {
      setWorking(false);
    }
  }

  // D44: resolution is its own explicit action. It takes its own
  // confirmation, and neither replying nor handing back reaches it. It is
  // idempotent server-side, so a lost race resolves as a no-op rather than an
  // error the owner has to understand.
  async function handleResolve() {
    await confirm({
      title: "Resolve this conversation?",
      description:
        "This marks the conversation resolved and removes it from Action needed. Any new customer reply reopens it.",
      confirmLabel: "Resolve",
      onConfirm: resolveConversation,
    });
  }

  async function resolveConversation() {
    setWorking(true);
    setError(null);
    const message = resolveDraft.trim();
    try {
      await apiFetch(`/api/conversations/${id}/resolve`, {
        method: "POST",
        body: JSON.stringify({ message: message || null }),
      });
      setResolveDraft("");
      setResolveOpen(false);
      await invalidateConversationLists(queryClient);
      // The stamp and the optional message are in the transcript now; refetch
      // immediately instead of waiting out the poll interval.
      setReloadToken((token) => token + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "That didn't go through.");
    } finally {
      setWorking(false);
    }
  }

  // T-029 (D35): the owner deletes one customer conversation. The server
  // refuses one that has a quote attached; that reason is shown as written.
  async function handleDelete() {
    setDeleteError(null);
    await confirm({
      title: "Delete this conversation?",
      description: "The conversation and its messages are deleted permanently. This cannot be undone.",
      confirmLabel: "Delete",
      tone: "danger",
      onConfirm: remove,
    });
  }

  async function remove() {
    try {
      await apiFetch(`/api/conversations/${id}`, { method: "DELETE" });
    } catch (err) {
      setDeleteError(err instanceof ApiError ? err.detail : "Could not delete this conversation.");
      return;
    }
    // The console layout re-polls the list every 4s, but until that tick the
    // deleted row would still show, and opening it lands on a not-found.
    await invalidateConversationLists(queryClient);
    toast.success("Conversation deleted");
    router.replace("/chats");
  }

  // Built from the route id, not the response, so the title is right on first
  // paint instead of flashing a placeholder while the detail request is out.
  const customerName = customerLabel(detail?.customer_ref, id);

  return (
    <div className="flex h-full min-h-0 flex-col bg-bg">
      <ScreenTopbar
        title={customerName}
        backHref="/chats"
        action={
          detail ? (
            <button
              type="button"
              aria-label="Delete conversation"
              data-testid="delete-conversation"
              disabled={working}
              onClick={() => void handleDelete()}
              className="flex size-icon-btn items-center justify-center rounded-full text-text transition-colors duration-(--duration-fast) hover:bg-surface-container active:bg-surface-container-high disabled:opacity-50"
            >
              <Icon name="delete" size={20} />
            </button>
          ) : undefined
        }
      />
      <Container className="flex min-h-0 flex-1 flex-col">
      <p
        data-testid="thread-status"
        className={`pb-2 text-footnote ${takenOver ? "text-text-secondary" : "text-accent-active"}`}
      >
        {statusLine()}
      </p>
      {detail?.customer_email ? (
        <p data-testid="thread-email" className="-mt-2 pb-2 text-footnote text-text-tertiary">
          {detail.customer_email}
        </p>
      ) : null}

      <div className="flex flex-1 flex-col gap-2 overflow-y-auto pb-4">
        {detail?.messages.map((message) => (
          <div key={message.id} className="flex flex-col gap-1">
            <ChatBubble role={message.role as never} perspective="operator">
              {message.role === "system" ? (
                // The prototype's `thr-pill`: a centred stamp with the time it
                // happened, so the history says who was speaking and from when.
                <span className="inline-block rounded-full bg-bubble-in px-3 py-1">
                  {message.content}
                  <span className="text-text-tertiary"> · {clockTime(message.created_at)}</span>
                </span>
              ) : (
                message.content
              )}
            </ChatBubble>
            <div className="max-w-[85%] self-end">
              <StructuredResponse response={message.metadata.response} />
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {error ? <p className="pb-2 text-footnote text-danger">{error}</p> : null}
      {deleteError ? (
        <p data-testid="delete-error" className="pb-2 text-footnote text-danger">
          {deleteError}
        </p>
      ) : null}

      {settled ? null : (
        <div className="shrink-0 border-t border-hairline pb-[max(1rem,env(safe-area-inset-bottom))] pt-3">
          <div className="mb-3">
            {resolveOpen ? (
              <div className="flex flex-col gap-2">
                <textarea
                  data-testid="resolve-message"
                  aria-label="Message to the customer (optional)"
                  value={resolveDraft}
                  onChange={(e) => setResolveDraft(e.target.value)}
                  placeholder="Optional message to the customer…"
                  rows={3}
                  className="w-full rounded-md border border-border bg-surface px-3 py-2 text-body-sm text-text placeholder:text-text-tertiary transition-colors duration-(--duration-fast) hover:border-border-strong"
                />
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    data-testid="resolve-submit"
                    loading={working}
                    onClick={() => void handleResolve()}
                  >
                    Resolve
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    data-testid="resolve-cancel"
                    disabled={working}
                    onClick={() => {
                      setResolveOpen(false);
                      setResolveDraft("");
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <Button
                size="sm"
                variant="secondary"
                data-testid="resolve-issue"
                disabled={working}
                onClick={() => setResolveOpen(true)}
              >
                Resolve conversation
              </Button>
            )}
          </div>
          <div className="mb-3 text-center">
            <button
              type="button"
              disabled={working}
              data-testid={takenOver ? "hand-back" : "take-over"}
              onClick={() => void handleTakeover()}
              className="inline-block rounded-full bg-accent-subtle px-4 py-2 text-chip font-medium text-accent-active transition-[filter] duration-(--duration-fast) hover:brightness-95 active:brightness-90 disabled:opacity-50"
            >
              {takenOver ? "Hand back to Agencx" : "Take over this conversation"}
            </button>
          </div>
          {takenOver ? (
            <CommandPill
              value={draft}
              onChange={setDraft}
              placeholder="Type a message…"
              disabled={working}
              onSubmit={(text) => {
                setDraft("");
                void act("reply", { message: text });
              }}
            />
          ) : null}
        </div>
      )}
      </Container>
      {confirmDialog}
    </div>
  );
}
