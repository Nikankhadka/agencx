import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { CustomerChatPanel } from "./CustomerChatPanel";

/**
 * RF-8 presentation selection. The repo has no jsdom, so effects (and therefore
 * `useMediaQuery`) do not run under `renderToStaticMarkup`; the hook is mocked
 * to force each presentation and the markup/ARIA each one produces is pinned
 * here. Live behavior (scroll, page interactivity, focus) is covered by
 * `e2e/rf-8-desktop-chat-panel.spec.ts`.
 */
vi.mock("@/lib/useMediaQuery", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/useMediaQuery")>()),
  useMediaQuery: vi.fn(() => false),
}));
import { useMediaQuery } from "@/lib/useMediaQuery";

function html(open: boolean): string {
  return renderToStaticMarkup(
    <CustomerChatPanel open={open} onClose={() => {}} title="Chat with Bytefix">
      <p>thread</p>
    </CustomerChatPanel>,
  );
}

describe("CustomerChatPanel desktop presentation", () => {
  it("is a complementary landmark, not a modal dialog", () => {
    vi.mocked(useMediaQuery).mockReturnValue(true);
    const markup = html(true);

    expect(markup).toContain('role="complementary"');
    expect(markup).toContain('aria-label="Chat with Bytefix"');
    expect(markup).not.toContain('role="dialog"');
    expect(markup).not.toContain("aria-modal");
    // No scrim element: the page behind stays visible.
    expect(markup).not.toContain("bg-scrim");
  });

  it("has a close control and slides in from the right when open", () => {
    vi.mocked(useMediaQuery).mockReturnValue(true);
    const markup = html(true);

    expect(markup).toContain('aria-label="Close chat"');
    expect(markup).toContain("translate-x-0");
    expect(markup).not.toContain("translate-x-full");
  });

  it("hides (unmount-free) when closed", () => {
    vi.mocked(useMediaQuery).mockReturnValue(true);
    const markup = html(false);

    // Children stay mounted so the thread is never orphaned.
    expect(markup).toContain("thread");
    expect(markup).toContain("translate-x-full");
  });
});

describe("CustomerChatPanel mobile presentation", () => {
  it("is a full-height modal sheet with scrim and aria-modal", () => {
    vi.mocked(useMediaQuery).mockReturnValue(false);
    const markup = html(true);

    expect(markup).toContain('role="dialog"');
    expect(markup).toContain('aria-modal="true"');
    expect(markup).toContain("h-dvh");
    expect(markup).toContain("bg-scrim");
    // The mobile sheet is the modal one, so it is not a complementary landmark.
    expect(markup).not.toContain('role="complementary"');
  });

  it("keeps the page content mounted while closed", () => {
    vi.mocked(useMediaQuery).mockReturnValue(false);
    expect(html(false)).toContain("thread");
  });
});
