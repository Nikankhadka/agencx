"use client";

import { useRef, useState } from "react";
import { CommandPill } from "@/components/ui/CommandPill";
import { Chip } from "@/components/ui/Chip";
import { FieldPill } from "@/components/ui/FieldPill";
import { PhonePill } from "@/components/ui/PhonePill";
import { formatAbn } from "@/lib/abn";
import {
  ACCEPTED_UPLOAD_EXTENSIONS,
  type InputSpec,
  type WidgetKind,
} from "@/lib/onboarding";

export interface BeatComposerProps {
  /** The widget the server wants for this beat. */
  input: InputSpec;
  busy: boolean;
  onText: (text: string) => void;
  onSelection: (values: string[], label: string) => void;
  onStop: () => void;
  /** Files picked through the pill's "+" (O-3); omitted, the affordance is inert. */
  onFiles?: (files: File[]) => void;
  /**
   * The address the owner logged in with. Rendered as a one-tap chip on any
   * beat whose InputSpec asks for it - the server declares the chip, the client
   * supplies the value, because only the client has it.
   */
  ownerEmail?: string | null;
}

/**
 * The per-beat composer, ported from `buildCmdPill(placeholder, onSubmit,
 * chips)` in the ONBOARDING section of agencx-prototype-v6.html.
 *
 * Layout follows the prototype exactly: a `.chips-row` sits **above** the pill
 * inside the same widget, never beside or below it, and the pill is always
 * there. Chips are an accelerator, never a gate - "or type…" is the
 * placeholder, and typing past them always works.
 *
 * O-12: fixed server chips submit their declared value through the selection
 * protocol. The server advances the draft and question together, so the
 * composer cannot remain on an older beat.
 *
 * A chip carrying `widget` is the exception - it swaps the composer to that
 * widget and sends nothing until that widget's own value is submitted. That is
 * how the country-code phone pill and the welded ABN pill arrive, without this
 * component ever knowing which beat it is on.
 *
 * The pill's "+" opens a file picker when `onFiles` is given (O-3): uploads
 * belong to the conversation, so there is no dropzone and no uploads screen.
 * The root fades up in 80ms on beat change (remounted via its `key` in page.tsx).
 */
export function BeatComposer({
  input,
  busy,
  onText,
  onSelection,
  onStop,
  onFiles,
  ownerEmail,
}: BeatComposerProps) {
  const [text, setText] = useState("");
  const [masked, setMasked] = useState("");
  // Which widget a chip has swapped us into, if any. No reset needed on beat
  // change: page.tsx remounts this component on `key={stage}`.
  const [swapped, setSwapped] = useState<WidgetKind | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  function submitText(value: string) {
    const trimmed = value.trim();
    if (!trimmed || busy) return;
    setText("");
    onText(trimmed);
  }

  const kind = swapped ?? input.kind;

  const chips = [
    ...(input.suggest_owner_email && ownerEmail
      ? [
          {
            label: ownerEmail,
            value: ownerEmail,
            dashed: false,
            widget: null,
            serverOwned: false,
          },
        ]
      : []),
    ...input.chips.map((chip) => ({ ...chip, serverOwned: true })),
  ];

  return (
    <div
      className="animate-beat-in flex flex-col gap-2.5"
      data-testid="onboarding-composer"
    >
      {/* `.chips-row` - above the pill, in the same widget, wrapping. It stays
          up after a widget swap, so a beat is never a trap: tapping the active
          chip again drops back to the pill, and the other chips still answer.
          The prototype needs an edit pencil on the sent bubble for this; here
          the chips have not gone anywhere, so they can just be the way back. */}
      {chips.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {chips.map((chip) => (
            <Chip
              key={chip.value}
              label={chip.label}
              dashed={chip.dashed}
              selected={chip.widget != null && chip.widget === swapped}
              disabled={busy}
              data-testid={`onboarding-chip-${chip.value}`}
              onClick={() => {
                if (!chip.widget) {
                  if (chip.serverOwned) onSelection([chip.value], chip.label);
                  else submitText(chip.label);
                }
                else
                  setSwapped((prev) =>
                    prev === chip.widget ? null : (chip.widget ?? null),
                  );
              }}
            />
          ))}
        </div>
      ) : null}

      {kind === "phone" ? (
        <PhonePill disabled={busy} onSubmit={(value) => submitText(value)} />
      ) : kind === "masked" ? (
        <FieldPill
          value={masked}
          onChange={(value) => setMasked(formatAbn(value))}
          onSubmit={(value) => onSelection([value], value)}
          placeholder={input.mask ?? ""}
          disabled={busy}
          canSubmit={masked.replace(/\D/g, "").length === 11}
          inputMode="numeric"
          type="tel"
          aria-label={input.prefix ?? "Number"}
          data-testid="onboarding-masked-input"
          leading={
            input.prefix ? (
              // `.abn-pre` is `font:500 13px/1` - the same type spec as a chip.
              <span className="py-3.5 pl-5 pr-3 text-chip font-medium text-ink-a40">
                {input.prefix}
              </span>
            ) : null
          }
        />
      ) : (
        <>
          <CommandPill
            value={text}
            onChange={setText}
            onSubmit={submitText}
            placeholder={input.placeholder}
            disabled={busy}
            busy={busy}
            onStop={onStop}
            onAttach={onFiles ? () => fileRef.current?.click() : undefined}
          />
          {/* The thread has no dropzone - the prototype attaches from inside the
              pill, so the picker is a hidden input the "+" opens. */}
          <input
            ref={fileRef}
            type="file"
            multiple
            accept={ACCEPTED_UPLOAD_EXTENSIONS.join(",")}
            className="hidden"
            data-testid="onboarding-file-input"
            onChange={(event) => {
              if (event.target.files) onFiles?.(Array.from(event.target.files));
              event.target.value = "";
            }}
          />
        </>
      )}
    </div>
  );
}
