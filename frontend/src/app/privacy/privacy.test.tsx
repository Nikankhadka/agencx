import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import TermsPage from "../terms/page";
import PrivacyPage from "./page";

/**
 * The two legal pages carry claims that other code makes true (retention
 * windows, the request path, the quote rule), so what they say is pinned here:
 * the numbers must match docs/agencx/design/retention.md, and the PRD section 13
 * copy rules apply even though the text is about a language model.
 */
const text = (node: React.ReactElement) =>
  renderToStaticMarkup(node)
    .replace(/<[^>]+>/g, " ")
    .replace(/&#x27;|&quot;/g, "'");

describe("privacy page", () => {
  const html = text(<PrivacyPage />);

  it("quotes the retention windows the retention module enforces", () => {
    expect(html).toContain("365 days after the last message");
    expect(html).toContain("after 30 days");
  });

  it("names every language model and processing provider, and the free-plan risk", () => {
    for (const name of [
      "Supabase",
      "Vercel",
      "Cloudinary",
      "Google AI Studio",
      "Groq",
      "OpenRouter",
      "Cohere",
      "Sentry",
    ]) {
      expect(html).toContain(name);
    }
    expect(html).toContain("free plan");
    expect(html).toContain("train");
  });

  it("promises the request window the operator process delivers", () => {
    expect(html).toContain("within 30 days");
  });
});

describe.each([
  ["privacy", <PrivacyPage key="p" />],
  ["terms", <TermsPage key="t" />],
])("%s copy rules", (_name, page) => {
  const html = text(page);

  it("avoids the words PRD section 13 keeps out of routine copy", () => {
    // "Google AI Studio" is a provider's name, not our wording for the assistant.
    expect(html.replace("Google AI Studio", "Google")).not.toMatch(
      /\b(AI|agents?|automated|virtual)\b/i,
    );
  });

  it("uses a plain dash, never an em dash", () => {
    expect(html).not.toContain(String.fromCharCode(0x2014));
  });
});

describe("terms", () => {
  it("says a quote is an estimate and that the model never produces a price", () => {
    const html = text(<TermsPage />);
    expect(html).toContain("A quote is an estimate, not an offer");
    expect(html).toContain("never produces a price");
  });
});
