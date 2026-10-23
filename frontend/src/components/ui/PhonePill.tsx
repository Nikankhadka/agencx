"use client";

import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type CSSProperties,
  type KeyboardEvent,
} from "react";
import { createPortal } from "react-dom";
import {
  COUNTRIES,
  DEFAULT_ISO,
  countryByIso,
  filterCountries,
  parseStoredPhone,
  resolveDefaultIso,
  toInternational,
  type Country,
  type StoredPhone,
} from "@/lib/phone";
import { FieldPill } from "./FieldPill";

/**
 * The country-code phone input: a dial-code button welded into the pill's left
 * edge, a searchable popover covering every region libphonenumber knows, live
 * national formatting, and an inline error that appears only after a failed
 * submit.
 *
 * The prototype used this to collect a number for an SMS code. Agencx does not
 * send SMS (decision 6 - login is a free email code), so here it collects the
 * number customers should ring, which is a different thing wearing the same
 * widget. The value is stored in international human format ("+61 412 345
 * 678"), not E.164, because the onboarding answer is also the chat message the
 * agent reads and the Business page renders verbatim.
 */

export interface PhonePillProps {
  disabled?: boolean;
  /** Receives the dial code and number as one string, e.g. "+61 412 345 678". */
  onSubmit?: (value: string) => void;
  /**
   * The initial full value ("+61 412 345 678"). Read once on mount; the pill
   * owns the draft from there and reports every keystroke through `onChange`.
   * Callers that switch the saved value show a new pill (the contact sheet is
   * keyed by the saved contact), which is how a reset reaches it.
   */
  value?: string;
  onChange?: (value: string) => void;
  /** Hide the send circle when a surrounding form owns submission. */
  showSubmit?: boolean;
  /** Override the field test id where this widget is reused outside onboarding. */
  testId?: string;
  /**
   * Where the country panel opens. "up" is right when the pill sits at the
   * bottom of the screen (the onboarding composer); a form near the top of a
   * sheet passes "down".
   */
  menuPlacement?: "up" | "down";
}

const subscribeToLocale = () => () => {};
const getLocaleIso = () => resolveDefaultIso(navigator.languages);
const getServerIso = () => DEFAULT_ISO;

export function PhonePill({
  disabled,
  onSubmit,
  value,
  onChange,
  showSubmit = true,
  testId = "onboarding-phone-input",
  menuPlacement = "up",
}: PhonePillProps) {
  const controlled = value !== undefined;
  const [initial] = useState<StoredPhone | null>(() =>
    controlled ? parseStoredPhone(value ?? "") : null,
  );
  const [pickedIso, setPickedIso] = useState<string | null>(null);
  const [storedIso] = useState<string | null>(initial?.country.iso ?? null);
  const [local, setLocal] = useState(initial?.local ?? "");
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(-1);
  const [showError, setShowError] = useState(false);
  const [anchorRect, setAnchorRect] = useState<DOMRect | null>(null);

  const wrapRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const phoneRef = useRef<HTMLInputElement>(null);
  const listId = useId();

  // Server renders the anchor market, then the browser's region takes over
  // after hydration without a mismatch warning. A stored value always wins.
  const localeIso = useSyncExternalStore(subscribeToLocale, getLocaleIso, getServerIso);
  const countryIso = pickedIso ?? storedIso ?? localeIso;
  const country = countryByIso(countryIso) ?? COUNTRIES[0];
  const valid = country.valid(local);
  const filtered = useMemo(() => filterCountries(query), [query]);

  const measure = useCallback(() => {
    const rect = wrapRef.current?.getBoundingClientRect();
    if (!rect) return;
    if (rect.bottom < 0 || rect.top > window.innerHeight) {
      setOpen(false);
      return;
    }
    setAnchorRect(rect);
  }, []);

  // The prototype closes the picker on any document click. The panel lives in
  // a portal, so it is outside the wrapper and has to be checked separately.
  useEffect(() => {
    if (!open) return;
    function onDocClick(event: MouseEvent) {
      const target = event.target as Node;
      if (!wrapRef.current?.contains(target) && !panelRef.current?.contains(target)) {
        setOpen(false);
      }
    }
    document.addEventListener("click", onDocClick);
    return () => document.removeEventListener("click", onDocClick);
  }, [open]);

  // The panel is fixed-positioned against the pill, so it follows the pill on
  // page and sheet scroll without re-measuring for scrolls inside the panel.
  useEffect(() => {
    if (!open) return;
    function onViewportChange(event: Event) {
      const target = event.target;
      if (target instanceof Node && panelRef.current?.contains(target)) return;
      measure();
    }
    window.addEventListener("resize", onViewportChange);
    window.addEventListener("scroll", onViewportChange, true);
    return () => {
      window.removeEventListener("resize", onViewportChange);
      window.removeEventListener("scroll", onViewportChange, true);
    };
  }, [open, measure]);

  useEffect(() => {
    if (open) searchRef.current?.focus();
  }, [open]);

  // The alphabetical list starts at "Afghanistan"; open on the current country.
  useEffect(() => {
    if (!open) return;
    document
      .getElementById(`${listId}-${countryIso}`)
      ?.scrollIntoView({ block: "nearest" });
  }, [open, listId, countryIso]);

  // Keep the keyboard-highlighted option inside the scroll area.
  useEffect(() => {
    if (!open || active < 0) return;
    const iso = filtered[active]?.iso;
    if (!iso) return;
    document.getElementById(`${listId}-${iso}`)?.scrollIntoView({ block: "nearest" });
  }, [active, filtered, open, listId]);

  function emit(next: string) {
    if (controlled) onChange?.(next);
  }

  function change(next: string) {
    setShowError(false);

    // A pasted or typed international number carries its own country. Parse it
    // before formatting; formatting it as a national number for the current
    // country would mangle it. A partial "+4" stays visible until it resolves.
    if (next.trimStart().startsWith("+")) {
      const parsed = parseStoredPhone(next);
      if (parsed) {
        setPickedIso(parsed.country.iso);
        setLocal(parsed.local);
        emit(toInternational(parsed.local, parsed.country.iso));
      } else {
        setLocal(next);
        emit(next);
      }
      return;
    }

    const formatted = country.format(next);
    setLocal(formatted);
    emit(toInternational(formatted, country.iso));
  }

  function pick(next: Country) {
    setPickedIso(next.iso);
    setLocal("");
    setOpen(false);
    setQuery("");
    setActive(-1);
    setShowError(false);
    emit(next.code);
    phoneRef.current?.focus();
  }

  function openPicker() {
    if (disabled) return;
    if (open) {
      setOpen(false);
      return;
    }
    const rect = wrapRef.current?.getBoundingClientRect();
    if (!rect) return;
    setAnchorRect(rect);
    setQuery("");
    setActive(-1);
    setOpen(true);
  }

  function searchKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
      phoneRef.current?.focus();
      return;
    }
    // Focus stays in the search field: options are not tab stops, so Tab
    // closes the popover and hands focus back to the phone field inside the
    // surrounding sheet instead of escaping its focus trap.
    if (event.key === "Tab") {
      event.preventDefault();
      setOpen(false);
      phoneRef.current?.focus();
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((current) =>
        filtered.length === 0 ? -1 : Math.min(current + 1, filtered.length - 1),
      );
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((current) => Math.max(current - 1, 0));
      return;
    }
    if (event.key === "Enter") {
      // Enter on a search result picks the highlighted row, or the top match
      // when the owner has typed a query but not pressed an arrow key yet.
      const index = active >= 0 ? active : query.trim() ? 0 : -1;
      const choice = filtered[index];
      if (choice) {
        event.preventDefault();
        pick(choice);
      }
    }
  }

  function panelStyle(rect: DOMRect): CSSProperties {
    const margin = 8;
    const width = Math.min(320, window.innerWidth - margin * 2);
    const left = Math.min(Math.max(rect.left, margin), window.innerWidth - width - margin);
    const space =
      menuPlacement === "up"
        ? rect.top - margin * 2
        : window.innerHeight - rect.bottom - margin * 2;
    const maxHeight = Math.max(160, Math.min(360, space));
    return menuPlacement === "up"
      ? {
          position: "fixed",
          left,
          width,
          maxHeight,
          bottom: window.innerHeight - rect.top + margin,
        }
      : {
          position: "fixed",
          left,
          width,
          maxHeight,
          top: rect.bottom + margin,
        };
  }

  // The panel is portalled out of the surrounding sheet: the sheet's content
  // area scrolls, and an in-flow popover on its first field would be clipped
  // before a single country was visible.
  const panel =
    open && anchorRect && typeof document !== "undefined"
      ? createPortal(
          <div
            ref={panelRef}
            style={panelStyle(anchorRect)}
            className="z-[60] flex flex-col overflow-hidden rounded-lg bg-surface shadow-popover"
          >
            <div className="shrink-0 border-b border-ink-a07 p-2">
              <input
                ref={searchRef}
                type="text"
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value);
                  setActive(-1);
                }}
                onKeyDown={searchKeyDown}
                placeholder="Search country"
                aria-label="Search countries"
                role="combobox"
                aria-expanded="true"
                aria-controls={listId}
                aria-autocomplete="list"
                aria-activedescendant={
                  active >= 0 && filtered[active]
                    ? `${listId}-${filtered[active].iso}`
                    : undefined
                }
                autoComplete="off"
                spellCheck={false}
                data-testid="phone-country-search"
                className="w-full rounded-field bg-surface-container px-3 py-2 text-body-sm text-text outline-none placeholder:text-ink-a40"
              />
            </div>
            <ul
              id={listId}
              role="listbox"
              aria-label="Country"
              className="min-h-0 flex-1 overflow-y-auto"
            >
              {filtered.length === 0 ? (
                <li className="px-4 py-3 text-body-sm text-ink-a40">No countries found</li>
              ) : (
                filtered.map((option, index) => (
                  <li key={option.iso}>
                    <button
                      type="button"
                      role="option"
                      id={`${listId}-${option.iso}`}
                      tabIndex={-1}
                      aria-selected={option.iso === country.iso}
                      onMouseEnter={() => setActive(index)}
                      onClick={() => pick(option)}
                      className={[
                        "flex w-full items-center gap-3 px-4 py-3 text-left text-body-sm text-text transition-colors duration-(--duration-fast)",
                        index === active ? "bg-surface-container" : "hover:bg-ink-a05",
                        option.iso === country.iso ? "font-medium" : "",
                      ].join(" ")}
                    >
                      <span aria-hidden="true">{option.flag}</span>
                      <span>{option.name}</span>
                      <span className="ml-auto text-ink-a40">{option.code}</span>
                    </button>
                  </li>
                ))
              )}
            </ul>
          </div>,
          document.body,
        )
      : null;

  return (
    <div ref={wrapRef} className="relative">
      {panel}

      <FieldPill
        value={local}
        onChange={change}
        onSubmit={() => onSubmit?.(toInternational(local, country.iso))}
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
        inputRef={phoneRef}
        leading={
          <button
            type="button"
            disabled={disabled}
            onClick={(event) => {
              event.stopPropagation();
              openPicker();
            }}
            aria-label={`Country: ${country.name}`}
            aria-haspopup="listbox"
            aria-expanded={open}
            className="flex select-none items-center gap-1 py-4 pl-5 pr-3 text-body-sm font-medium text-accent-active transition-colors duration-(--duration-fast) hover:underline active:opacity-60 disabled:opacity-50"
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
              Please enter a valid phone number for {country.name}.
            </p>
          ) : null
        }
      />
    </div>
  );
}
