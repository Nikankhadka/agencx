"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import ChatsQueue from "./ChatsQueue";

/**
 * RF-15: Chats is a split pane at `lg+` - the queue list on the left, the
 * conversation thread on the right - with no navigation between them. Below
 * `lg` the two panes are the old list-then-thread: selecting a row shows the
 * full-height thread and hides the list, with the console's bottom `TabBar`
 * still standing over both.
 *
 * A segment `layout.tsx` is the smallest correct home for the list: it renders
 * at both `/chats` and `/chats/[id]`, so the list stays mounted while the route
 * changes underneath it, which is the whole point of the desktop pane. Parallel
 * routes were rejected as more structure than the requirement earns (D1).
 *
 * Visibility is route plus breakpoint CSS only - `usePathname()` says whether a
 * thread is open, and the `lg` classes decide what a wide viewport does with
 * that. No JS media query: the browser never needs to know the breakpoint, just
 * to apply it (D2). The root is `overflow-hidden`: the console layout already
 * wraps children in an `overflow-y-auto` region, and the list and thread scroll
 * inside their own panes, so without it the two would produce double scrollbars.
 */

export default function ChatsLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  // `/chats` is the list; `/chats/<id>` is a thread. EndsWith would be wrong for
  // a future deeper route, and this is the same prefix rule the console nav uses.
  const threadOpen = pathname.startsWith("/chats/");

  return (
    <div className="flex h-full min-h-0 w-full overflow-hidden">
      <div
        data-testid="chats-list-pane"
        className={[
          "min-h-0 flex-col bg-bg w-full lg:w-(--width-queue) lg:border-r lg:border-hairline",
          threadOpen ? "hidden lg:flex" : "flex",
        ].join(" ")}
      >
        <ChatsQueue />
      </div>
      <div
        data-testid="chats-thread-pane"
        className={[
          "min-h-0 flex-1 bg-bg",
          threadOpen ? "flex flex-col" : "hidden lg:flex lg:flex-col",
        ].join(" ")}
      >
        {children}
      </div>
    </div>
  );
}
