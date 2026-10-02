"use client";

import { useEffect, useState } from "react";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { RowLink } from "@/components/ui/RowLink";
import { ScreenTopbar } from "@/components/ui/ScreenTopbar";
import { abnSummary } from "@/lib/abn";
import { apiFetch, ApiError } from "@/lib/api";
import { useScrollRestoration } from "@/lib/useScrollRestoration";
import type { BusinessProfile, ProfileUpdate } from "@/lib/api-schemas";
import { AbnSheet } from "./components/AbnSheet";
import { ContactSheet } from "./components/ContactSheet";
import { ProfileFieldSheet } from "./components/ProfileFieldSheet";
import { ServicesSheet, servicesSummary } from "./components/ServicesSheet";
import { VoiceSheet, voiceSummary } from "./components/VoiceSheet";

const EMPTY: BusinessProfile = {
  name: "",
  hours: "",
  description: "",
  business_contact: "",
  abn: "",
  gst: "",
  services: [],
  customer_voice_preset: "warm_casual",
  customer_voice_custom_style: "",
};

type Editing = "name" | "hours" | "description" | "contact" | "abn" | "voice" | "services";

/** A row summary: the saved value, or the invitation to fill it. */
function orPlaceholder(value: string, placeholder: string): string {
  return value.trim() || placeholder;
}

/**
 * Business details, built from `renderScreen('business')` in agencx-prototype-v6.html:
 * a topbar over a list of `.bh-row`s. Some open a screen, some open an edit
 * sheet - the prototype's list does both, and this one does too.
 *
 * Still not a settings tree. RF-2 makes the business identity correctable here:
 * name, hours, description and contact, each a sheet over the same profile save
 * path as ABN and services. The rest of the profile is written once at confirm.
 * The prototype's remaining sections (pricing, payment mode, channels) belong
 * to Stage 2 work that does not exist, and a row that opens onto nothing is
 * worse than an absent one.
 */
export default function BusinessDetailsPage() {
  const [profile, setProfile] = useState<BusinessProfile>(EMPTY);
  // Which sheet is open, if any - the rows share one save path and one error.
  const [editing, setEditing] = useState<Editing | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { confirm, dialog: confirmDialog } = useConfirm();
  const scrollRef = useScrollRestoration<HTMLDivElement>("/business/details");

  useEffect(() => {
    apiFetch<BusinessProfile>("/api/business/profile")
      .then(setProfile)
      .catch(() => setProfile(EMPTY));
  }, []);

  async function save(next: ProfileUpdate) {
    setBusy(true);
    setError(null);
    try {
      // An empty ABN is the owner saying they do not have one, so GST goes
      // with it rather than being saved as an answer to a question that no
      // longer applies.
      const body = next.abn === "" ? { abn: "" } : next;
      setProfile(await apiFetch<BusinessProfile>("/api/business/profile", {
        method: "PATCH",
        body: JSON.stringify(body),
      }));
      setEditing(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "That didn't save. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex h-full min-h-0 flex-col overflow-hidden bg-surface">
      <ScreenTopbar title="Business details" backHref="/business" />
      <div
        ref={scrollRef}
        data-testid="business-details-scroll"
        className="min-h-0 flex-1 overflow-y-auto lg:mx-auto lg:w-full lg:max-w-thread pb-16"
      >
        <RowLink
          href="/business/details/knowledge"
          label="Knowledge"
          icon="folder_open"
          detail="Where your customers' answers come from"
        />
        <RowLink
          label="Business name"
          icon="dashboard"
          detail={orPlaceholder(profile.name, "Add your business name")}
          onClick={() => {
            setError(null);
            setEditing("name");
          }}
        />
        <RowLink
          label="Opening hours"
          icon="refresh"
          detail={orPlaceholder(profile.hours, "Add your opening hours")}
          onClick={() => {
            setError(null);
            setEditing("hours");
          }}
        />
        <RowLink
          label="Description"
          icon="edit"
          detail={orPlaceholder(profile.description, "Add a short description")}
          onClick={() => {
            setError(null);
            setEditing("description");
          }}
        />
        <RowLink
          label="Business contact"
          icon="support_agent"
          detail={orPlaceholder(profile.business_contact, "Add how customers reach you")}
          onClick={() => {
            setError(null);
            setEditing("contact");
          }}
        />
        <RowLink
          label="ABN & Tax"
          icon="verified_user"
          detail={abnSummary(profile)}
          onClick={() => {
            setError(null);
            setEditing("abn");
          }}
        />
        <RowLink
          label="Assistant voice"
          icon="forum"
          detail={voiceSummary(profile)}
          onClick={() => {
            setError(null);
            setEditing("voice");
          }}
        />
        <RowLink
          label="Services"
          icon="sell"
          detail={servicesSummary(profile)}
          onClick={() => {
            setError(null);
            setEditing("services");
          }}
        />
      </div>
      <ProfileFieldSheet
        open={editing === "name"}
        field="name"
        title="Edit business name"
        label="Business name"
        value={profile.name}
        placeholder="Bytefix Repairs"
        busy={busy}
        error={error}
        onClose={() => setEditing(null)}
        onSave={save}
      />
      <ProfileFieldSheet
        open={editing === "hours"}
        field="hours"
        title="Edit opening hours"
        label="Opening hours"
        value={profile.hours}
        placeholder="Mon to Fri 9am to 6pm"
        busy={busy}
        error={error}
        onClose={() => setEditing(null)}
        onSave={save}
      />
      <ProfileFieldSheet
        open={editing === "description"}
        field="description"
        title="Edit description"
        label="Description"
        value={profile.description}
        placeholder="What your business does, in your own words"
        multiline
        busy={busy}
        error={error}
        onClose={() => setEditing(null)}
        onSave={save}
      />
      <ContactSheet
        open={editing === "contact"}
        profile={profile}
        busy={busy}
        error={error}
        onClose={() => setEditing(null)}
        onSave={save}
      />
      <ServicesSheet
        open={editing === "services"}
        profile={profile}
        busy={busy}
        error={error}
        onClose={() => setEditing(null)}
        onSave={save}
        confirmRemove={confirm}
      />
      <AbnSheet
        open={editing === "abn"}
        profile={profile}
        busy={busy}
        error={error}
        onClose={() => setEditing(null)}
        onSave={save}
      />
      <VoiceSheet
        open={editing === "voice"}
        profile={profile}
        busy={busy}
        error={error}
        onClose={() => setEditing(null)}
        onSave={save}
      />
      {confirmDialog}
    </main>
  );
}
