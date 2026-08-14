"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { CommandPill } from "@/components/ui/CommandPill";
import { Icon } from "@/components/ui/Icon";
import { Input } from "@/components/ui/Input";
import { isMultiSelect, type InputSpec } from "@/lib/onboarding";

export interface BeatComposerProps {
  /** The widget the server wants for this beat. */
  input: InputSpec;
  busy: boolean;
  onText: (text: string) => void;
  onSelect: (values: string[]) => void;
  onStop: () => void;
}

/**
 * The per-beat composer. Renders exactly the widget the server's InputSpec
 * asks for (text / chips / masked / cta), so the frontend never guesses what a
 * beat wants - the beat system in app/onboarding/beats.py is the single source
 * of truth. Chip and masked selections submit as deterministic ``selection``
 * messages (no LLM); only text beats stream.
 *
 * Multi-select is signalled by dashed chips (inbound channels): chips toggle
 * and a Continue button commits the set. The root fades up in 80ms on beat
 * change (remounted via its ``key`` in page.tsx).
 */
export function BeatComposer({
  input,
  busy,
  onText,
  onSelect,
  onStop,
}: BeatComposerProps) {
  const [text, setText] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [masked, setMasked] = useState("");

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
    <div className="[animation:beat-in_80ms_ease-out]" data-testid="onboarding-composer">
      {input.kind === "text" ? (
        <CommandPill
          value={text}
          onChange={setText}
          onSubmit={handleTextSubmit}
          placeholder={input.placeholder}
          disabled={busy}
          busy={busy}
          onStop={onStop}
        />
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
        <div className="flex flex-col gap-3">
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
        <div className="flex flex-col gap-3">
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
        <div className="flex flex-col gap-3">
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
