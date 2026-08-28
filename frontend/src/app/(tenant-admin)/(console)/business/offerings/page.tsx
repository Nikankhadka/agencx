"use client";

import { ScreenTopbar } from "@/components/ui/ScreenTopbar";
import { OfferingsList } from "../components/OfferingsList";

/**
 * M-1/M-4: "What you offer" - the owner's own offerings, on their own screen.
 *
 * M-1 first mounted `OfferingsList` inline on the Business hub. M-4 gave it a
 * row of its own instead, because the hub is a list of places (D21) and a hub
 * that is partly a list of places and partly an editor reads as neither. The
 * list component is unchanged; only where it hangs moved.
 */
export default function OfferingsPage() {
  return (
    <main className="flex h-full min-h-0 flex-col overflow-hidden bg-surface">
      <ScreenTopbar title="What you offer" backHref="/business" />
      <div className="min-h-0 flex-1 overflow-y-auto pb-20 lg:mx-auto lg:w-full lg:max-w-thread">
        <OfferingsList />
      </div>
    </main>
  );
}
