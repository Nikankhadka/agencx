import type { HTMLAttributes } from "react";

export interface ContainerProps extends HTMLAttributes<HTMLDivElement> {
  /** Content column: "thread" (640, default) or "wide" (1024). */
  width?: "thread" | "wide";
}

const WIDTH_CLASSES = {
  thread: "max-w-thread",
  wide: "max-w-5xl",
} as const;

/**
 * The centered page column. ScreenTopbar is full-bleed with px-gutter, so
 * content in a Container aligns under it. The width prop picks the column;
 * className is for layout only.
 */
export function Container({ width = "thread", className = "", ...rest }: ContainerProps) {
  return (
    <div
      className={["mx-auto w-full px-gutter", WIDTH_CLASSES[width], className].join(" ")}
      {...rest}
    />
  );
}
