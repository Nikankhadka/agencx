"use client";

import { RowLink } from "@/components/ui/RowLink";
import { ScreenTopbar } from "@/components/ui/ScreenTopbar";
import { Icon } from "@/components/ui/Icon";
import { useAuth } from "@/components/AuthProvider";

/**
 * E-1 / D21: Business, the third tab - a hub of places, built from
 * `renderScreen('business')` in agencx-prototype-v6.html (`.bh-row`: icon,
 * label, chevron). The hub shape is the point: Stage 2 adds Schedule, Money
 * and Plan as rows here, so growth costs a row rather than a re-cut of the
 * navigation.
 *
 * One row today, the same call `/settings` made when it shipped: the
 * prototype's other rows open onto Stage 2 machinery that does not exist, and
 * a row that opens onto nothing is worse than an absent one (PRD, "never build
 * dead surfaces"). E-5 adds the Booking page.
 *
 * Sign-out lives here because the hamburger drawer that used to hold it is
 * gone (E-1): on a phone the sidebar never renders, and sign-out must stay
 * reachable.
 */
export default function BusinessPage() {
  const { signOut } = useAuth();
  return (
    <main className="flex h-full min-h-0 flex-col overflow-hidden bg-surface">
      <ScreenTopbar title="Business" back={false} />
      <div className="min-h-0 flex-1 overflow-y-auto lg:mx-auto lg:w-full lg:max-w-thread">
        <RowLink
          href="/settings"
          label="Settings"
          icon="settings"
          detail="What your assistant knows"
        />
        <button
          type="button"
          onClick={() => signOut()}
          className="flex w-full items-center gap-3.5 border-b border-hairline px-gutter py-[15px] text-left transition-colors duration-(--duration-fast) active:bg-ink-a05 lg:hidden"
        >
          <span className="flex size-5 shrink-0 items-center justify-center text-ink-a40">
            <Icon name="logout" size={20} />
          </span>
          <span className="flex-1 text-row-label font-medium text-text">Sign out</span>
        </button>
      </div>
    </main>
  );
}
