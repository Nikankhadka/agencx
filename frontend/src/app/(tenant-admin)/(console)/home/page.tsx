"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

/**
 * E-1 / D21: Home, the tenant app's first tab and the place the owner lands
 * after go-live. This ticket builds the greeting and the surface it heads;
 * E-4 fills it with the brief - the things waiting on the owner right now.
 *
 * Ported from `#greeting` / `#greeting-h1` in agencx-prototype-v6.html.
 *
 * The prototype's home also carries a composer, and Stage 1 deliberately does
 * not: `POST /api/onboarding/message` 409s once onboarding is confirmed
 * (controller.py `run_message`), and no everyday owner-Copilot route replaces
 * it. A composer that errors on every send is worse than no composer, so the
 * affordance waits for the backend that answers it.
 */

interface OnboardingState {
  draft: Record<string, string>;
}

/** The prototype greets by time of day; the owner's name comes from O-1. */
function greetingFor(date: Date): string {
  const hour = date.getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export default function HomePage() {
  const [name, setName] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<OnboardingState>("/api/onboarding/state")
      .then((state) => setName(state.draft?.["name"]?.trim() || null))
      .catch(() => setName(null));
  }, []);

  return (
    <main className="flex h-full min-h-0 flex-col overflow-y-auto bg-surface px-gutter pt-thread-top">
      <h1 className="text-greeting font-bold tracking-[var(--text-greeting-tracking)] text-text">
        {greetingFor(new Date())},
        <br />
        {name ?? "there"}.
      </h1>
    </main>
  );
}
