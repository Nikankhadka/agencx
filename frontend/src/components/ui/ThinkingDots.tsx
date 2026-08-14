import type { CSSProperties } from "react";

/**
 * docs/design/prototypes/design.md: three pulsing dots inside the assistant
 * bubble while a turn is pending. Prototype values: 7px dots, 5px gap, 1.3s
 * ease-in-out loop, 220ms stagger, -2.5px travel (keyframe `thinking-dot` in
 * globals.css). Decorative only (aria-hidden); the global prefers-reduced-
 * motion guard zeroes the animation.
 */
const dotStyle = (delay: string): CSSProperties => ({
  animation: "thinking-dot 1.3s ease-in-out infinite",
  animationDelay: delay,
});

export function ThinkingDots() {
  return (
    <span aria-hidden="true" className="flex items-center gap-[5px]">
      <span className="h-[7px] w-[7px] rounded-full bg-text-secondary" style={dotStyle("0ms")} />
      <span className="h-[7px] w-[7px] rounded-full bg-text-secondary" style={dotStyle("220ms")} />
      <span className="h-[7px] w-[7px] rounded-full bg-text-secondary" style={dotStyle("440ms")} />
    </span>
  );
}
