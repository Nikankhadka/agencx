import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { CustomerChat } from "./CustomerChat";

/**
 * RF-11 static markup. The repository has no jsdom and `renderToStaticMarkup`
 * does not run effects, so this can only pin the initial, live-composer
 * presentation. The terminal-state decision (escalated hides the control) is
 * the extracted `shouldShowAskForPerson` predicate, unit-tested in
 * `@/lib/handoff.test.ts`; the live tap and the already-open case are covered
 * by `e2e/rf-11-ask-for-a-person.spec.ts`.
 */
function html(): string {
  return renderToStaticMarkup(
    <CustomerChat
      slug="bytefix"
      displayName="Bytefix Repairs"
      greeting={null}
      starterQuestions={[]}
    />,
  );
}

describe("RF-11 Ask for a person control", () => {
  it("renders a named control in the live composer", () => {
    const markup = html();
    // The accessible name comes from the Chip's label text; it is exactly
    // "Ask for a person".
    expect(markup).toContain("Ask for a person");
    expect(markup).toContain('data-testid="ask-for-person"');
  });
});
