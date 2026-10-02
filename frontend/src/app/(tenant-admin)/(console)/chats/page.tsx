"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { EmptyState } from "@/components/ui/EmptyState";
import { Icon } from "@/components/ui/Icon";
import { ListRow, RowIdentity } from "@/components/ui/ListRow";
import { ScreenTopbar } from "@/components/ui/ScreenTopbar";
import { Container } from "@/components/ui/Container";
import { useApiQuery, errorMessage } from "@/lib/useApiQuery";
import { useScrollRestoration } from "@/lib/useScrollRestoration";
import type { ConversationSummary } from "@/lib/api-schemas";
import { customerLabel, relativeTime } from "@/lib/format";

/**
 * C-6 Chats: every customer conversation, and which ones want the owner.
 *
 * This is the owner's queue. The Escalations table still exists for the
 * Wren-era console, but an owner does not think in escalation rows - they think
 * "who is waiting on me?", which is what the Action needed filter answers. Each
 * row carries the assistant's own one-line summary of what the customer wants,
 * so triage happens here rather than by opening four threads.
 *
 * Ported from agencx-prototype-v6.html's `chats` screen: filter row, `chat-row`
 * with name / time / status / preview, and the search bar. Mounted chrome-free
 * until E-1 builds the tab bar to hold it. Two departures from the prototype,
 * both because it only ever mocked named customers: the row falls back to the
 * conversation's short reference rather than a literal "Customer" every row
 * shares, and the amber attention dot is a labelled pill.
 */

type Filter = "all" | "action" | "unread";

const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "action", label: "Action needed" },
  { id: "unread", label: "Unread" },
];

/**
 * The line under the name. The assistant's summary of what the customer wants
 * beats the last message whenever there is one - "Balance outstanding 4 days.
 * Send a reminder?" tells the owner more than whatever was said most recently.
 */
function previewOf(row: ConversationSummary): string {
  return row.pending_summary?.trim() || row.last_message?.trim() || "No messages yet";
}

export default function ChatsPage() {
  const router = useRouter();
  const query = useApiQuery<ConversationSummary[]>("/api/conversations");
  const scrollRef = useScrollRestoration<HTMLDivElement>("/chats");
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");
  const [searching, setSearching] = useState(false);

  const rows = useMemo(() => {
    const all = query.data ?? [];
    const byFilter = all.filter((row) => {
      if (filter === "action") return row.needs_attention;
      // "Unread" is honestly approximated as "the customer spoke last" - there
      // is no per-owner read state yet, and inventing a table for it before the
      // tab bar exists would be building the wrong thing first.
      if (filter === "unread") return row.needs_attention || row.status === "human";
      return true;
    });
    const needle = search.trim().toLowerCase();
    if (!needle) return byFilter;
    return byFilter.filter((row) =>
      `${customerLabel(row.customer_ref, row.id)} ${previewOf(row)}`.toLowerCase().includes(needle)
    );
  }, [query.data, filter, search]);

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
        {FILTERS.map((option) => (
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
          </button>
        ))}
      </div>

      <div ref={scrollRef} data-testid="chats-list" className="flex-1 overflow-y-auto">
        {query.error ? (
          <p className="py-4 text-body-sm text-danger">{errorMessage(query.error, "Could not load your chats.")}</p>
        ) : null}
        {!query.error && rows.length === 0 ? (
          <EmptyState
            icon="forum"
            title={search ? "No conversations found." : "No conversations yet."}
            description={
              search
                ? "Try a different name or word."
                : "When a customer messages you, the conversation shows up here."
            }
          />
        ) : null}
        {rows.map((row) => (
          <ListRow
            key={row.id}
            testId="chat-row"
            className="border-b border-hairline py-4 transition-colors duration-(--duration-fast) hover:bg-surface-container active:bg-ink-a05"
            onClick={() => router.push(`/chats/${row.id}`)}
            leading={<RowIdentity label={customerLabel(row.customer_ref, row.id)} />}
            title={customerLabel(row.customer_ref, row.id)}
            // The prototype's `.chat-row` preview is one line; the meta slot
            // itself does not clamp (Home's waiting rows use two), so the list
            // that wants one line says so here.
            meta={<span className="block truncate">{previewOf(row)}</span>}
            trailing={
              <>
                <span className="text-footnote text-text-secondary">
                  {relativeTime(row.last_activity_at ?? row.created_at)}
                </span>
                {/* A compact amber exclamation badge, not a text pill: the
                    words live in the filter chip above, and spelling them out
                    per row stole the title's width on a phone. Berry dot = the
                    assistant is handling it itself. Nothing = nothing
                    pending. */}
                {row.needs_attention ? (
                  <span
                    data-testid="row-attention"
                    role="img"
                    aria-label="Action needed"
                    title="Action needed"
                    className="grid size-5 place-items-center rounded-full bg-highlight text-text"
                  >
                    <Icon name="priority_high" size={14} />
                  </span>
                ) : row.status === "open" ? (
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
      </div>
      </Container>
    </div>
  );
}
