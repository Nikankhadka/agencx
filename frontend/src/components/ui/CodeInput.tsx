"use client";

import { useRef, type ClipboardEvent, type KeyboardEvent } from "react";

export interface CodeInputProps {
  value: string;
  onChange: (value: string) => void;
  onComplete: (code: string) => void;
  disabled?: boolean;
}

const LENGTH = 6;

/**
 * The six-digit login-code input (S1 login-in-chat). Six single-digit cells,
 * first auto-focused, numeric keyboard on mobile, auto-submit when six digits
 * are filled. Backspace moves back; paste spreads a six-digit string across the
 * cells.
 */
export function CodeInput({ value, onChange, onComplete, disabled }: CodeInputProps) {
  const refs = useRef<(HTMLInputElement | null)[]>([]);

  function setDigit(index: number, digit: string) {
    const next = value.split("");
    next[index] = digit;
    const joined = next.join("");
    onChange(joined);
    if (digit && index < LENGTH - 1) {
      refs.current[index + 1]?.focus();
    } else if (digit && joined.length === LENGTH && /^\d{6}$/.test(joined)) {
      onComplete(joined);
    }
  }

  function handleKeyDown(index: number, event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Backspace" && !value[index] && index > 0) {
      refs.current[index - 1]?.focus();
    }
  }

  function handlePaste(event: ClipboardEvent<HTMLInputElement>) {
    const text = event.clipboardData.getData("text").replace(/\D/g, "").slice(0, LENGTH);
    if (text.length === LENGTH) {
      event.preventDefault();
      onChange(text);
      onComplete(text);
    }
  }

  return (
    <div className="flex gap-2" aria-label="6-digit code">
      {Array.from({ length: LENGTH }, (_, index) => (
        <input
          key={index}
          ref={(el) => {
            refs.current[index] = el;
          }}
          value={value[index] ?? ""}
          onChange={(event) => {
            const digit = event.target.value.replace(/\D/g, "").slice(-1);
            setDigit(index, digit);
          }}
          onKeyDown={(event) => handleKeyDown(index, event)}
          onPaste={handlePaste}
          inputMode="numeric"
          autoComplete="one-time-code"
          aria-label={`Digit ${index + 1}`}
          disabled={disabled}
          autoFocus={index === 0}
          className="h-12 w-10 rounded-md border border-border bg-surface text-center text-title-3 font-semibold text-text outline-none focus:border-accent focus:ring-2 focus:ring-accent disabled:opacity-50"
        />
      ))}
    </div>
  );
}
