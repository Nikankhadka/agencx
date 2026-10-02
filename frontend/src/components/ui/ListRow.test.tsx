import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { ListRow, RowIdentity } from "./ListRow";

/**
 * RF-1. The row grammar is a product decision: an owner reads every console
 * list the same way - identity or icon, the primary line, the quiet meta line,
 * the trailing action - so the slot order and the element each row becomes are
 * pinned here rather than left to whichever screen built its own row.
 */
describe("ListRow", () => {
  it("renders the grammar in order: leading, title, meta, trailing", () => {
    const html = renderToStaticMarkup(
      <ListRow
        leading={<span data-testid="lead" />}
        title="Business page"
        meta="What customers see"
        trailing={<span data-testid="tail" />}
      />,
    );
    const positions = ["lead", "Business page", "What customers see", "tail"].map((needle) =>
      html.indexOf(needle),
    );
    expect(positions.every((position) => position >= 0)).toBe(true);
    expect(positions).toEqual([...positions].sort((left, right) => left - right));
  });

  it("uses a link with href, a button with onClick, a div otherwise", () => {
    expect(renderToStaticMarkup(<ListRow href="/business" title="Business" />)).toContain("<a ");
    expect(renderToStaticMarkup(<ListRow onClick={() => {}} title="Sign out" />)).toContain(
      "<button",
    );
    expect(renderToStaticMarkup(<ListRow title="Static" />)).toContain("<div");
  });

  it("marks each slot so screens can align on one grammar", () => {
    const html = renderToStaticMarkup(<ListRow title="T" meta="M" trailing="X" />);
    expect(html).toContain('data-slot="title"');
    expect(html).toContain('data-slot="meta"');
    expect(html).toContain('data-slot="trailing"');
    // No leading node, no leading slot - the slot is optional, not empty chrome.
    expect(html).not.toContain('data-slot="leading"');
  });
});

describe("RowIdentity", () => {
  it("shows the first letter of a name", () => {
    const html = renderToStaticMarkup(<RowIdentity label="Emma W." />);
    expect(html).toContain(">E<");
  });

  it("falls back to a conversation glyph for an anonymous reference", () => {
    const html = renderToStaticMarkup(<RowIdentity label="#customer" />);
    expect(html).toContain("<svg");
    expect(html).not.toContain(">#<");
  });
});
