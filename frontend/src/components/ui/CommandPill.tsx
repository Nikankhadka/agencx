"use client";

import { useLayoutEffect, useRef, type KeyboardEvent } from "react";
import { Icon } from "./Icon";

export interface CommandPillProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  /** Streaming a reply - swap the send circle for a Stop square. */
  busy?: boolean;
  onStop?: () => void;
  /** Attach affordance (file/URL upload beat); hidden when omitted. */
  onAttach?: () => void;
}

const MAX_HEIGHT_PX = 96;

/**
 * The per-beat composer. A textarea that auto-grows to 96px (Enter submits, Shift+Enter newlines), a
 * "+" affordance on the left (18px), and a right cluster that swaps between
 * nothing (empty), a 34px filled send circle (non-empty), and a Stop square
 * (busy). Spread-ring shadow via --shadow-pill, not a border.
 */
export function CommandPill({
  value,
  onChange,
  onSubmit,
  placeholder,
  disabled,
  busy,
  onStop,
  onAttach,
}: CommandPillProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-grow, capped at MAX_HEIGHT_PX. Reset to auto first so shrinking the
  // text also shrinks the box (scrollHeight is otherwise sticky at the max).
  useLayoutEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT_PX)}px`;
  }, [value]);

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (value.trim() && !busy && !disabled) onSubmit(value);
    }
  }

  const hasText = value.trim().length > 0;

  return (
    <div className="flex items-end gap-2 rounded-pill bg-surface py-[11px] pl-[18px] pr-[10px] shadow-pill">
      <button
        type="button"
        onClick={onAttach}
        disabled={!onAttach}
        aria-label="Attach"
        className="mb-0.5 flex h-[18px] w-[18px] shrink-0 items-center justify-center text-text-tertiary disabled:opacity-50"
      >
        <Icon name={onAttach ? "attach_file" : "add"} size={18} />
      </button>
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        rows={1}
        className="max-h-24 min-h-6 flex-1 resize-none bg-transparent text-body leading-6 text-text placeholder:text-text-tertiary outline-none disabled:opacity-50"
      />
      {busy ? (
        <button
          type="button"
          onClick={onStop}
          aria-label="Stop"
          className="flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-full bg-accent text-text-inverse active:opacity-85"
        >
          <span className="h-2.5 w-2.5 rounded-[2px] bg-current" aria-hidden="true" />
        </button>
      ) : hasText ? (
        <button
          type="button"
          onClick={() => onSubmit(value)}
          disabled={disabled}
          aria-label="Send"
          className="flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-full bg-accent text-text-inverse active:opacity-85"
        >
          <Icon name="arrow_upward" size={20} />
        </button>
      ) : null}
    </div>
  );
}
