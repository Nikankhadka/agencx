"use client";

import { RowLink } from "@/components/ui/RowLink";
import { ScreenTopbar } from "@/components/ui/ScreenTopbar";

/**
 * Settings, built from `renderScreen('business')` in agencx-prototype-v6.html:
 * a topbar over a list of `.bh-row`s, each one a place to go. Not a settings
 * tree - the prototype has no toggles here, and neither does this.
 *
 * One row today. The prototype's other sections (pricing, payment mode, ABN,
 * channels) belong to Stage 2 work that does not exist yet, and a row that
 * opens onto nothing is worse than an absent one.
 */
export default function SettingsPage() {
  return (
    <main className="flex h-full min-h-0 flex-col overflow-hidden bg-surface">
      <ScreenTopbar title="Settings" backHref="/business" />
      <div className="min-h-0 flex-1 overflow-y-auto lg:mx-auto lg:w-full lg:max-w-thread pb-20">
        <RowLink
          href="/settings/knowledge"
          label="Knowledge"
          icon="folder_open"
          detail="Where your customers' answers come from"
        />
      </div>
    </main>
  );
}
