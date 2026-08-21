"use client";

import { useEffect, useRef, useState, type ClipboardEvent, type KeyboardEvent } from "react";

export interface CodeInputProps {
  value: string;
  onChange: (value: string) => void;
  onComplete: (code: string) => void;
  disabled?: boolean;
}

const LENGTH = 6;

const empty = (): string[] => Array.from({ length: LENGTH }, () => "");

/**
 * The six-digit login-code input (S1 login-in-chat). Six single-digit cells,
 * first auto-focused, numeric keyboard on mobile, auto-submit when six digits
 * are filled. Backspace moves back; paste spreads a six-digit string across the
 * cells.
 *
 * The cells are the source of truth, held as a fixed-length array mirrored in a
 * ref. Deriving the next code from the `value` prop instead would break under
 * fast input - a password manager, or any autofill that writes several cells
 * within one React batch - because each cell's handler would still read the
 * pre-update prop, and because `value.split("")` collapses the gaps in a
 * partly-filled code and so misaligns every later digit.
 */
export function CodeInput({ value, onChange, onComplete, disabled }: CodeInputProps) {
  const refs = useRef<(HTMLInputElement | null)[]>([]);
  const [digits, setDigits] = useState<string[]>(empty);
  const digitsRef = useRef<string[]>(digits);

  // The parent clears `value` to reset the cells (e.g. after a wrong code).
  useEffect(() => {
    if (value === "" && digitsRef.current.some(Boolean)) {
      digitsRef.current = empty();
      setDigits(digitsRef.current);
    }
  }, [value]);

  function commit(next: string[]) {
    digitsRef.current = next;
    setDigits(next);
    const joined = next.join("");
    onChange(joined);
    if (next.every((digit) => /^\d$/.test(digit))) {
      onComplete(joined);
    }
  }

  function setDigit(index: number, digit: string) {
    const next = [...digitsRef.current];
    next[index] = digit;
    commit(next);
    if (digit && index < LENGTH - 1) {
      refs.current[index + 1]?.focus();
    }
  }

  function handleKeyDown(index: number, event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Backspace" && !digitsRef.current[index] && index > 0) {
      refs.current[index - 1]?.focus();
    }
  }

  function handlePaste(event: ClipboardEvent<HTMLInputElement>) {
    const text = event.clipboardData.getData("text").replace(/\D/g, "").slice(0, LENGTH);
    if (text.length === LENGTH) {
      event.preventDefault();
      commit(text.split(""));
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
          value={digits[index] ?? ""}
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
