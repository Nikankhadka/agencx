"use client";

import { useEffect, useRef, useState } from "react";
import { FieldPill } from "./FieldPill";

/**
 * The country-code phone input, ported from `initPhone()` and the `COUNTRIES`
 * table in agencx-prototype-v6.html: a dial-code button welded into the pill's
 * left edge, a popover that opens upward, per-country formatting and
 * validation, and an inline error that appears only after a failed submit.
 *
 * The prototype uses this to collect a number for an SMS code. Agencx does not
 * send SMS (decision 6 - login is a free email code), so here it collects the
 * number customers should ring, which is a different thing wearing the same
 * widget.
 */

interface Country {
  code: string;
  flag: string;
  name: string;
  /** Live display formatting as the owner types. */
  format: (value: string) => string;
  valid: (value: string) => boolean;
  placeholder: string;
}

const digitsOf = (value: string) => value.replace(/\D/g, "");

export const COUNTRIES: Country[] = [
  {
    code: "+61",
    flag: "🇦🇺",
    name: "Australia",
    format: (value) => {
      const d = digitsOf(value).slice(0, 10);
      if (d.length <= 4) return d;
      if (d.length <= 7) return `${d.slice(0, 4)} ${d.slice(4)}`;
      return `${d.slice(0, 4)} ${d.slice(4, 7)} ${d.slice(7)}`;
    },
    valid: (value) => /^0[45]\d{8}$/.test(digitsOf(value)),
    placeholder: "0412 345 678",
  },
  {
    code: "+64",
    flag: "🇳🇿",
    name: "New Zealand",
    format: (value) => value,
    valid: (value) => digitsOf(value).length >= 8,
    placeholder: "Phone number",
  },
  {
    code: "+1",
    flag: "🇺🇸",
    name: "United States",
    format: (value) => {
      const d = digitsOf(value).slice(0, 10);
      if (d.length <= 3) return d;
      if (d.length <= 6) return `(${d.slice(0, 3)}) ${d.slice(3)}`;
      return `(${d.slice(0, 3)}) ${d.slice(3, 6)}-${d.slice(6)}`;
    },
    // NANP area codes never start with 0 or 1; the rest is the 10-digit check.
    valid: (value) => /^[2-9]\d{9}$/.test(digitsOf(value)),
    placeholder: "(555) 123-4567",
  },
  {
    code: "+44",
    flag: "🇬🇧",
    name: "United Kingdom",
    format: (value) => value,
    valid: (value) => digitsOf(value).length >= 10,
    placeholder: "Phone number",
  },
  {
    code: "+65",
    flag: "🇸🇬",
    name: "Singapore",
    format: (value) => value,
    valid: (value) => digitsOf(value).length >= 8,
    placeholder: "Phone number",
  },
  {
    code: "+977",
    flag: "🇳🇵",
    name: "Nepal",
    format: (value) => {
      const d = digitsOf(value).slice(0, 10);
      if (d.length <= 4) return d;
      if (d.length <= 7) return `${d.slice(0, 4)} ${d.slice(4)}`;
      return `${d.slice(0, 4)} ${d.slice(4, 7)} ${d.slice(7)}`;
    },
    // Nepali mobiles are 10 digits and start 96 to 99.
    valid: (value) => /^9[6-9]\d{8}$/.test(digitsOf(value)),
    placeholder: "9812 345 678",
  },
];

export interface PhonePillProps {
  disabled?: boolean;
  /** Receives the dial code and number as one string, e.g. "+61 0412 345 678". */
  onSubmit?: (value: string) => void;
  /**
   * Controlled full value ("+61 0412 345 678"). Given, the pill reports every
   * keystroke through `onChange` instead of holding its own draft, for forms
   * whose Save owns submission. Omitted, it is the self-contained onboarding
   * beat.
   */
  value?: string;
  onChange?: (value: string) => void;
  /** Hide the send circle when a surrounding form owns submission. */
  showSubmit?: boolean;
  /** Override the field test id where this widget is reused outside onboarding. */
  testId?: string;
}

/** Splits a stored "+61 0412 345 678" back into its country and local number. */
function decode(value: string): { country: Country; local: string } {
  const trimmed = value.trimStart();
  const match = COUNTRIES.find((entry) => trimmed.startsWith(entry.code));
  if (!match) return { country: COUNTRIES[0], local: "" };
  return { country: match, local: trimmed.slice(match.code.length).trimStart() };
}

export function PhonePill({
  disabled,
  onSubmit,
  value,
  onChange,
  showSubmit = true,
  testId = "onboarding-phone-input",
}: PhonePillProps) {
  const controlled = value !== undefined;
  const [countryState, setCountry] = useState<Country>(COUNTRIES[0]);
  const [valueState, setValue] = useState("");
  const [open, setOpen] = useState(false);
  const [showError, setShowError] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const decoded = controlled ? decode(value) : null;
  const country = decoded?.country ?? countryState;
  const local = decoded?.local ?? valueState;

  // The prototype closes the picker on any document click.
  useEffect(() => {
    if (!open) return;
    function onDocClick(event: MouseEvent) {
      if (!wrapRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("click", onDocClick);
    return () => document.removeEventListener("click", onDocClick);
  }, [open]);

  const valid = country.valid(local);

  function change(next: string) {
    setShowError(false);
    const formatted = country.format(next);
    if (controlled) onChange?.(`${country.code} ${formatted}`.trimEnd());
    else setValue(formatted);
  }

  function pick(next: Country) {
    setCountry(next);
    setOpen(false);
    setShowError(false);
    // Switching country clears the field: a number formatted for one country is
    // not a draft of a number for another.
    if (controlled) onChange?.(next.code);
    else setValue("");
  }

  return (
    <div ref={wrapRef} className="relative">
      {open ? (
        <ul
          role="listbox"
          aria-label="Country"
          className="absolute bottom-[calc(100%+8px)] left-0 z-30 min-w-[220px] overflow-hidden rounded-lg bg-surface shadow-popover"
        >
          {COUNTRIES.map((option) => (
            <li key={option.code}>
              <button
                type="button"
                role="option"
                aria-selected={option.code === country.code}
                onClick={() => pick(option)}
                className="flex w-full items-center gap-3 px-4 py-3 text-left text-body-sm text-text transition-colors duration-(--duration-fast) hover:bg-ink-a05"
              >
                <span aria-hidden="true">{option.flag}</span>
                <span>{option.name}</span>
                <span className="ml-auto text-ink-a40">{option.code}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <FieldPill
        value={local}
        onChange={change}
        onSubmit={() => onSubmit?.(`${country.code} ${local.trim()}`)}
        placeholder={country.placeholder}
        disabled={disabled}
        canSubmit={valid}
        onRejected={() => setShowError(true)}
        showSubmit={showSubmit}
        type="tel"
        inputMode="tel"
        autoComplete="tel"
        aria-label="Phone number"
        data-testid={testId}
        leading={
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              setOpen((prev) => !prev);
            }}
            aria-label={`Country: ${country.name}`}
            aria-expanded={open}
            className="flex select-none items-center gap-1 py-4 pl-5 pr-3 text-body-sm font-medium text-accent-active transition-colors duration-(--duration-fast) hover:underline active:opacity-60"
          >
            <span aria-hidden="true">{country.flag}</span>
            <span>{country.code}</span>
          </button>
        }
        // The error appears only after a rejected send, never while typing: the
        // dimmed circle is the live signal, and scolding someone mid-keystroke
        // for a number they have not finished typing is the thing to avoid.
        below={
          showError && !valid ? (
            <p role="alert" className="px-1 text-meta text-danger">
              Please enter a valid mobile number for {country.name}.
            </p>
          ) : null
        }
      />
    </div>
  );
}
