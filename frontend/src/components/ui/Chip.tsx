"use client";

import type { ButtonHTMLAttributes } from "react";

export interface ChipProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "onClick"> {
  label: string;
  value?: string;
  /** Dashed suggestion chip (multi-select hints). */
  dashed?: boolean;
  /** Read-only "sent" chip - records a committed selection, no interaction. */
  sent?: boolean;
  /** Toggle state for multi-select chips (e.g. inbound channels). */
  selected?: boolean;
  onClick?: () => void;
}

const BASE = [
  "inline-flex min-h-11 items-center justify-center gap-2",
  "border-[length:var(--border-chip)] border-accent-subtle",
  "text-chip font-medium transition-colors duration-fast select-none",
  "active:bg-accent-subtle",
].join(" ");

const VARIANT_CLASSES = {
  solid: "text-accent px-[14px] hover:bg-accent-subtle",
  dashed: "border-dashed text-accent px-4 hover:bg-accent-subtle",
  sent: "pointer-events-none text-text-tertiary px-[14px]",
} as const;

/**
 * The enum-shaped beat widget. Three variants - solid (selectable), dashed
 * (suggestion), sent (committed). 1.5px border via --border-chip, radius
 * --radius-chip, 44px min target (an intentional deviation from the earlier
 * ~29px chips).
 */
export function Chip({
  label,
  dashed,
  sent,
  selected,
  disabled,
  className = "",
  onClick,
  ...rest
}: ChipProps) {
  const variant = sent ? "sent" : dashed ? "dashed" : "solid";
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-pressed={selected ? true : undefined}
      className={[BASE, VARIANT_CLASSES[variant], selected ? "bg-accent-subtle" : "", className].join(
        " ",
      )}
      {...rest}
    >
      {label}
    </button>
  );
}
