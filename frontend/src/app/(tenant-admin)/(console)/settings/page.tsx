"use client";

import { useEffect, useState } from "react";
import { RowLink } from "@/components/ui/RowLink";
import { ScreenTopbar } from "@/components/ui/ScreenTopbar";
import { abnSummary } from "@/lib/abn";
import { apiFetch, ApiError } from "@/lib/api";
import { AbnSheet, type BusinessProfile } from "./components/AbnSheet";

const EMPTY: BusinessProfile = { abn: "", gst: "" };

/**
 * Business details, built from `renderScreen('business')` in agencx-prototype-v6.html:
 * a topbar over a list of `.bh-row`s. Some open a screen, some open an edit
 * sheet - the prototype's list does both, and this one does too.
 *
 * Still not a settings tree. The rest of the profile the interview captured -
 * business name, hours, what you offer, how customers reach you - is written
 * once at go-live and has no editor here yet; the ABN row exists because the
 * interview now asks for two fields no screen was ever showing back. The
 * prototype's remaining sections (pricing, payment mode, channels) belong to
 * Stage 2 work that does not exist, and a row that opens onto nothing is worse
 * than an absent one.
 */
export default function BusinessDetailsPage() {
  const [profile, setProfile] = useState<BusinessProfile>(EMPTY);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<BusinessProfile>("/api/business/profile")
      .then(setProfile)
      .catch(() => setProfile(EMPTY));
  }, []);

  async function save(next: BusinessProfile) {
    setBusy(true);
    setError(null);
    try {
      // An empty ABN is the owner saying they do not have one, so GST goes
      // with it rather than being saved as an answer to a question that no
      // longer applies.
      const body = next.abn ? next : { abn: "" };
      setProfile(await apiFetch<BusinessProfile>("/api/business/profile", {
        method: "PATCH",
        body: JSON.stringify(body),
      }));
      setEditing(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "That didn't save. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex h-full min-h-0 flex-col overflow-hidden bg-surface">
      <ScreenTopbar title="Business details" backHref="/business" />
      <div className="min-h-0 flex-1 overflow-y-auto lg:mx-auto lg:w-full lg:max-w-thread pb-20">
        <RowLink
          href="/business/details/knowledge"
          label="Knowledge"
          icon="folder_open"
          detail="Where your customers' answers come from"
        />
        <RowLink
          label="ABN & Tax"
          icon="verified_user"
          detail={abnSummary(profile)}
          onClick={() => {
            setError(null);
            setEditing(true);
          }}
        />
      </div>
      <AbnSheet
        open={editing}
        profile={profile}
        busy={busy}
        error={error}
        onClose={() => setEditing(false)}
        onSave={save}
      />
    </main>
  );
}
