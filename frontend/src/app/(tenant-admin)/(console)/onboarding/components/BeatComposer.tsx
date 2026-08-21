"use client";

import { useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { CommandPill } from "@/components/ui/CommandPill";
import { Icon } from "@/components/ui/Icon";
import { Input } from "@/components/ui/Input";
import { ACCEPTED_UPLOAD_EXTENSIONS, isMultiSelect, type InputSpec } from "@/lib/onboarding";

export interface BeatComposerProps {
  /** The widget the server wants for this beat. */
  input: InputSpec;
  busy: boolean;
  onText: (text: string) => void;
  onSelect: (values: string[]) => void;
  onStop: () => void;
  /** Files picked through the pill's "+" (O-3); omitted, the affordance is inert. */
  onFiles?: (files: File[]) => void;
}

/**
 * The per-beat composer. Renders exactly the widget the server's InputSpec
 * asks for (text / chips / masked / cta), so the frontend never guesses what a
 * beat wants - the beat system in app/onboarding/beats.py is the single source
 * of truth. Chip and masked selections submit as deterministic ``selection``
 * messages (no LLM); only text beats stream.
 *
 * The pill's "+" opens a file picker when ``onFiles`` is given (O-3): uploads
 * belong to the conversation, so there is no dropzone and no uploads screen.
 *
 * Multi-select is signalled by dashed chips (inbound channels): chips toggle
 * and a Continue button commits the set. The root fades up in 80ms on beat
 * change (remounted via its ``key`` in page.tsx).
 *
 * Layout follows the prototype's ``buildCmdPill(placeholder, onSubmit, chips)``:
 * a chips row sits ABOVE the pill in the same widget, never beside or below it.
 * ``beats.py`` makes all seven lean beats text-only today, so in the live flow
 * only the text branch renders; the rest are kept because the InputSpec wire
 * contract still carries them.
 */
export function BeatComposer({
  input,
  busy,
  onText,
  onSelect,
  onStop,
  onFiles,
}: BeatComposerProps) {
  const [text, setText] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [masked, setMasked] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  function handleTextSubmit(value: string) {
    const trimmed = value.trim();
    if (!trimmed || busy) return;
    setText("");
    onText(trimmed);
  }

  function toggle(chipValue: string) {
    setSelected((prev) =>
      prev.includes(chipValue)
        ? prev.filter((v) => v !== chipValue)
        : [...prev, chipValue],
    );
  }

  function commitMasked() {
    const trimmed = masked.trim();
    if (trimmed) onSelect([trimmed]);
  }

  const multi = isMultiSelect(input);

  return (
    <div className="animate-beat-in flex flex-col gap-2.5" data-testid="onboarding-composer">
      {input.kind === "text" ? (
        <>
          <CommandPill
            value={text}
            onChange={setText}
            onSubmit={handleTextSubmit}
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
      ) : null}

      {input.kind === "chips" && !multi ? (
        <div className="flex flex-wrap gap-2">
          {input.chips.map((chip) => (
            <Chip
              key={chip.value}
              label={chip.label}
              data-testid={`onboarding-chip-${chip.value}`}
              disabled={busy}
              onClick={() => onSelect([chip.value])}
            />
          ))}
        </div>
      ) : null}

      {input.kind === "chips" && multi ? (
        <div className="flex flex-col gap-2.5">
          <div className="flex flex-wrap gap-2">
            {input.chips.map((chip) => (
              <Chip
                key={chip.value}
                label={chip.label}
                dashed
                selected={selected.includes(chip.value)}
                data-testid={`onboarding-chip-${chip.value}`}
                disabled={busy}
                onClick={() => toggle(chip.value)}
              />
            ))}
          </div>
          <div>
            <Button
              size="sm"
              disabled={busy || selected.length === 0}
              data-testid="onboarding-chip-continue"
              onClick={() => {
                onSelect(selected);
                setSelected([]);
              }}
            >
              Continue
            </Button>
          </div>
        </div>
      ) : null}

      {input.kind === "masked" ? (
        <div className="flex flex-col gap-2.5">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              commitMasked();
            }}
            className="flex items-end gap-2"
          >
            <div className="flex-1">
              <Input
                label="Business number"
                value={masked}
                onChange={(event) => setMasked(event.target.value)}
                placeholder={input.mask ?? ""}
                disabled={busy}
                inputMode="numeric"
                data-testid="onboarding-masked-input"
              />
            </div>
            <Button type="submit" disabled={busy || !masked.trim()}>
              Continue
            </Button>
          </form>
          {input.chips.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {input.chips.map((chip) => (
                <Chip
                  key={chip.value}
                  label={chip.label}
                  dashed
                  data-testid={`onboarding-chip-${chip.value}`}
                  disabled={busy}
                  onClick={() => onSelect([chip.value])}
                />
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      {input.kind === "cta" ? (
        <div className="flex flex-col gap-2.5">
          <div>
            <Button
              disabled={busy}
              data-testid="onboarding-cta"
              onClick={() => onSelect([])}
            >
              <span className="inline-flex items-center gap-2">
                <Icon name="verified_user" size={20} />
                {input.cta_label ?? "Continue"}
              </span>
            </Button>
          </div>
          {input.chips.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {input.chips.map((chip) => (
                <Chip
                  key={chip.value}
                  label={chip.label}
                  dashed
                  data-testid={`onboarding-chip-${chip.value}`}
                  disabled={busy}
                  onClick={() => onSelect([chip.value])}
                />
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
