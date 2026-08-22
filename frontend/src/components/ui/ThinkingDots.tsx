import type { CSSProperties } from "react";

/**
 * Three pulsing dots inside the assistant bubble while a turn is pending.
 * 7px accent dots, 5px gap, 1.3s ease-in-out loop, 220ms stagger, -2.5px travel
 * (keyframe `thinking-dot` in globals.css). Decorative only (aria-hidden);
 * the global prefers-reduced-motion guard zeroes the animation.
 *
 * P-5: this is the failover indicator. It is up from the moment the customer
 * sends until the first inspected token arrives, which spans the whole of
 * P-2's provider race - the loser is cancelled server-side and nothing about
 * the switch reaches the client, so the wait reads as thinking rather than as
 * mechanism. Nothing here needs to know that; the point is that nothing
 * interrupts it either.
 */
const dotStyle = (delay: string): CSSProperties => ({
  animation: "thinking-dot 1.3s ease-in-out infinite",
  animationDelay: delay,
});

export function ThinkingDots() {
  return (
    <span
      aria-hidden="true"
      data-testid="thinking-dots"
      className="flex items-center gap-[5px]"
    >
      <span className="h-[7px] w-[7px] rounded-full bg-accent" style={dotStyle("0ms")} />
      <span className="h-[7px] w-[7px] rounded-full bg-accent" style={dotStyle("220ms")} />
      <span className="h-[7px] w-[7px] rounded-full bg-accent" style={dotStyle("440ms")} />
    </span>
  );
}
