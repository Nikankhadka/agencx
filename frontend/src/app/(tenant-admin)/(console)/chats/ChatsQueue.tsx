"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { EmptyState } from "@/components/ui/EmptyState";
import { Icon } from "@/components/ui/Icon";
import { ListRow, RowIdentity } from "@/components/ui/ListRow";
import { ScreenTopbar } from "@/components/ui/ScreenTopbar";
import { Container } from "@/components/ui/Container";
import { errorMessage } from "@/lib/useApiQuery";
import { useScrollRestoration } from "@/lib/useScrollRestoration";
import type { ConversationSummary } from "@/lib/api-schemas";
import { customerLabel, relativeTime } from "@/lib/format";
import { FILTERS, waitingTimeOf, type QueueFilter } from "./lib/queue";
import { useConversationQueue, useDebounced } from "./lib/useConversationQueue";

/**
 * RF-14/D38 Chats: the owner's queue, filtered, searched, and paged on the
 * server over the whole tenant dataset.
 *
 * The old screen filtered the first 50 rows it held, so a busy tenant's older
 * unresolved issues hid behind a page bound that looked like a complete
 * answer. Now the tab is a server query (`filter=`), the search is a server
 * query (`q=`), and "Load more" counts down against a server `total`. Action
 * needed opens the screen because that is what an owner means by "who is
 * waiting on me?"; Unread, All, and Resolved sit beside it.
 *
 * Ported from agencx-prototype-v6.html's `chats` screen: the filter row,
 * `chat-row` with name / time / status / preview, and the search bar. The
 * amber attention indicator stays a compact exclamation badge; RF-18's unread
 * state bolds the name and carries a small accent dot, a separate axis. A
 * taken-over row names its handler ("You") where the assistant's brand dot
 * would otherwise sit, and a taken-over row the business spoke last on says
 * "Waiting on customer" instead of carrying the badge (D43).
 *
 * RF-15: the queue is its own component so the route-persistent `layout.tsx`
 * can keep it mounted as the left pane of the desktop split view - selecting a
 * row no longer unmounts the list.
 */

/** The line under the name. The assistant's summary of what the customer wants
 * beats the last message whenever there is one. */
function previewOf(row: ConversationSummary): string {
  return row.pending_summary?.trim() || row.last_message?.trim() || "No messages yet";
}

export default function ChatsQueue() {
  const router = useRouter();
  const scrollRef = useScrollRestoration<HTMLDivElement>("/chats");
  const [filter, setFilter] = useState<QueueFilter>("needs_you");
  const [search, setSearch] = useState("");
  const [searching, setSearching] = useState(false);
  // Settle the box before it becomes the query, so typing a name is one
  // request rather than one per keystroke.
  const debouncedSearch = useDebounced(search);
  const queue = useConversationQueue(filter, debouncedSearch);

  return (
    <div className="flex h-full min-h-0 flex-col bg-bg">
      <ScreenTopbar
        title="Chats"
        back={false}
        action={
          <button
            type="button"
            aria-label="Search conversations"
            onClick={() => {
              setSearching((open) => !open);
              setSearch("");
            }}
            className="flex size-icon-btn items-center justify-center rounded-full text-text transition-colors duration-(--duration-fast) hover:bg-surface-container active:bg-surface-container-high"
          >
            <Icon name="search" size={20} />
          </button>
        }
      />

      <Container className="flex min-h-0 flex-1 flex-col">
        {searching ? (
          <div className="border-b border-hairline py-2">
            <input
              autoFocus
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search conversations…"
              aria-label="Search conversations"
              data-testid="chats-search"
              className="w-full bg-transparent py-1 text-body-sm text-text outline-none placeholder:text-text-tertiary"
            />
          </div>
        ) : null}

        <div className="flex gap-2 overflow-x-auto py-3">
          {FILTERS.map((option) => {
            const count = queue.counts?.[option.id] ?? 0;
            return (
              <button
                key={option.id}
                type="button"
                onClick={() => setFilter(option.id)}
                aria-pressed={filter === option.id}
                data-testid={`chats-filter-${option.id}`}
                className={
                  filter === option.id
                    ? "shrink-0 rounded-chip border-chip border-accent-subtle bg-accent-subtle px-4 py-2 text-chip text-accent-active transition-colors duration-(--duration-fast)"
                    : "shrink-0 rounded-chip border-chip border-hairline px-4 py-2 text-chip text-text-secondary transition-colors duration-(--duration-fast) hover:bg-accent-a07 hover:text-accent-active active:bg-accent-a09"
                }
              >
                {option.label}
                {count > 0 ? (
                  <span
                    data-testid={`chats-filter-count-${option.id}`}
                    className="ml-1 tabular-nums"
                  >
                    {count}
                  </span>
                ) : null}
              </button>
            );
          })}
        </div>

        <div ref={scrollRef} data-testid="chats-list" className="flex-1 overflow-y-auto">
          {queue.error ? (
            <p className="py-4 text-body-sm text-danger">
              {errorMessage(queue.error, "Could not load your chats.")}
            </p>
          ) : null}
          {!queue.error && queue.items.length === 0 && !queue.isPending ? (
            <EmptyState
              icon="forum"
              title={debouncedSearch ? "No conversations found." : "No conversations yet."}
              description={
                debouncedSearch
                  ? "Try a different name or word."
                  : "When a customer messages you, the conversation shows up here."
              }
            />
          ) : null}
          {queue.items.map((row) => (
            <ListRow
              key={row.id}
              testId="chat-row"
              className="border-b border-hairline py-4 transition-colors duration-(--duration-fast) hover:bg-surface-container active:bg-ink-a05"
              onClick={() => router.push(`/chats/${row.id}`)}
              leading={<RowIdentity label={customerLabel(row.customer_ref, row.id)} />}
              unread={row.unread}
              title={customerLabel(row.customer_ref, row.id)}
              // The prototype's `.chat-row` preview is one line; the meta slot
              // itself does not clamp (Home's waiting rows use two), so the list
              // that wants one line says so here.
              meta={<span className="block truncate">{previewOf(row)}</span>}
              trailing={
                <>
                  <span className="text-footnote text-text-secondary">
                    {relativeTime(waitingTimeOf(row))}
                  </span>
                  {/* A compact amber exclamation badge, not a text pill: the
                      words live in the tab above, and spelling them out per row
                      stole the title's width on a phone. RF-14: handler and
                      attention are independent axes, so a thread with an open
                      escalation AND a human takeover shows both - the handler
                      names who is replying, the badge names that it still needs
                      the owner. */}
                  {row.needs_attention ? (
                    <span
                      data-testid="row-attention"
                      role="img"
                      aria-label="Needs you"
                      title="Needs you"
                      className="grid size-5 place-items-center rounded-full bg-highlight text-text"
                    >
                      <Icon name="priority_high" size={14} />
                    </span>
                  ) : null}
                  {row.waiting_on_customer ? (
                    <span
                      data-testid="row-waiting"
                      className="text-footnote text-text-tertiary"
                    >
                      Waiting on customer
                    </span>
                  ) : null}
                  {row.handler === "human" ? (
                    // A taken-over thread names its handler. The assistant's dot
                    // would be a lie here - the human is replying, not the
                    // assistant.
                    <span
                      data-testid="row-handler"
                      className="text-footnote font-medium text-accent-active"
                    >
                      You
                    </span>
                  ) : !row.needs_attention && row.status === "open" ? (
                    <span
                      role="img"
                      aria-label="Being handled for you"
                      className="size-[7px] rounded-full bg-accent"
                    />
                  ) : null}
                </>
              }
            />
          ))}

          {queue.hasMore ? (
            <button
              type="button"
              data-testid="chats-load-more"
              onClick={() => void queue.loadMore()}
              disabled={queue.isFetchingNextPage}
              className="my-4 w-full rounded-chip border-chip border-hairline px-4 py-3 text-chip text-text-secondary transition-colors duration-(--duration-fast) hover:bg-accent-a07 hover:text-accent-active active:bg-accent-a09 disabled:opacity-60"
            >
              {queue.isFetchingNextPage ? "Loading…" : "Load more"}
            </button>
          ) : null}
        </div>
      </Container>
    </div>
  );
}
