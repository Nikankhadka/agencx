/**
 * docs/design/frontend.md: ChatGPT-style "agent is working" indicator -
 * three staggered bouncing dots shown inside the assistant bubble while a
 * turn is pending but no prose has streamed in yet. Decorative only
 * (aria-hidden): the chat surfaces announce wait states through their own
 * live regions. Reduced motion is handled by the global
 * prefers-reduced-motion guard in globals.css, which zeroes the bounce.
 */
export function ThinkingDots() {
  return (
    <span aria-hidden="true" className="flex items-center gap-1">
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-text-secondary" />
      <span
        className="h-1.5 w-1.5 animate-bounce rounded-full bg-text-secondary"
        style={{ animationDelay: "150ms" }}
      />
      <span
        className="h-1.5 w-1.5 animate-bounce rounded-full bg-text-secondary"
        style={{ animationDelay: "300ms" }}
      />
    </span>
  );
}
