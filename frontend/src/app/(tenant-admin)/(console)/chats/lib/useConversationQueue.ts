"use client";

import { useEffect, useState } from "react";
import {
  useInfiniteQuery,
  type InfiniteData,
  type QueryClient,
} from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { ConversationCounts, ConversationListResponse } from "@/lib/api-schemas";
import { PAGE_SIZE, queuePath, type QueueFilter } from "./queue";

/**
 * The query-key namespace the queue list uses, keyed by `[filter, q]`. Every
 * cache-maintenance call (the thread marking a conversation read, deleting one)
 * invalidates by this prefix. The console layout and the hidden Wren
 * conversations screen key off the path (`["/api/conversations"]`) instead, so
 * both are invalidated together or the deleted/unread row lingers in whichever
 * one was missed.
 */
export const CONVERSATION_QUEUE_KEY = "conversations";

export function invalidateConversationLists(client: QueryClient): Promise<void> {
  return Promise.all([
    client.invalidateQueries({ queryKey: [CONVERSATION_QUEUE_KEY] }),
    client.invalidateQueries({ queryKey: ["/api/conversations"] }),
  ]).then(() => undefined);
}

/**
 * RF-14/D38: the Chats queue's server-driven list. One infinite query keyed by
 * `[filter, q]`, paging 50 rows at a time; the server total says whether more
 * remain, so "Load more" appends rather than guessing at a page boundary.
 *
 * The counts come from the first page - every page returns the same
 * whole-dataset counts (q applied, filter ignored), so reading page 0 keeps
 * the tabs stable while paging.
 */
export function useConversationQueue(filter: QueueFilter, q: string) {
  const query = useInfiniteQuery<
    ConversationListResponse,
    Error,
    InfiniteData<ConversationListResponse>,
    readonly unknown[],
    number
  >({
    queryKey: ["conversations", filter, q],
    queryFn: ({ pageParam }) => apiFetch<ConversationListResponse>(queuePath(filter, q, pageParam)),
    initialPageParam: 0,
    getNextPageParam: (lastPage, pages) => {
      const loaded = pages.length * PAGE_SIZE;
      return loaded < lastPage.total ? loaded : undefined;
    },
  });

  const items = query.data?.pages.flatMap((page) => page.items) ?? [];
  const total = query.data?.pages[0]?.total ?? 0;
  const counts: ConversationCounts | undefined = query.data?.pages[0]?.counts;

  return {
    items,
    total,
    counts,
    loaded: items.length,
    hasMore: query.hasNextPage,
    isPending: query.isPending,
    isFetchingNextPage: query.isFetchingNextPage,
    error: query.error,
    loadMore: query.fetchNextPage,
  };
}

/**
 * Debounce any value. The queue refetches from offset 0 on the server for
 * every keystroke otherwise, and a 300ms settling window is long enough that
 * typing a name is one request, not eight. Extracted from the hook so it can
 * be reused by later search surfaces.
 */
export function useDebounced<T>(value: T, delay = 300): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return settled;
}
