import type { HTMLAttributes } from "react";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** "none" (table/shell), "compact" p-4 (default), "roomy" p-6. */
  padding?: "none" | "compact" | "roomy";
}

const PADDING_CLASSES = {
  none: "",
  compact: "p-4",
  roomy: "p-6",
} as const;

/**
 * The app's one card: surface + hairline border + card radius. Elevation is
 * added by the caller as shadow-card; cards inside sheets stay flat. The
 * padding prop picks the recipe; className is for layout only.
 */
export function Card({ padding = "compact", className = "", ...rest }: CardProps) {
  return (
    <div
      className={["rounded-card border border-hairline bg-surface", PADDING_CLASSES[padding], className].join(
        " ",
      )}
      {...rest}
    />
  );
}
