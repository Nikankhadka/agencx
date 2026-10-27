import { afterEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import {
  discardConfirm,
  insertOwnerOffering,
  offeringPage,
  offeringPageCount,
  pageForOffering,
  Pagination,
  priceInputUpdate,
  reconcileLinkOfferings,
  removeOfferingConfirm,
  replaceLinkConfirm,
  profilePatchFor,
  ReviewSheet,
  toPendingOffering,
  toWorkingOffering,
  type ReviewProfile,
} from "./ReviewSheet";
import { offeringLabel } from "./offerings";
import type { KnowledgeRecord, ReviewOffering, ReviewWorkspace } from "./types";
import { useMediaQuery } from "@/lib/useMediaQuery";

// The repo has no jsdom (memory, 2026-10-03), so the media-query branch is
// selected by mocking the hook - spreading the real module so DESKTOP_QUERY
// survives the mock.
vi.mock("@/lib/useMediaQuery", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/useMediaQuery")>()),
  useMediaQuery: vi.fn(() => false),
}));

afterEach(() => {
  vi.mocked(useMediaQuery).mockReturnValue(false);
});

/**
 * W-6. What the owner is shown about a price is a product decision, not a
 * rendering detail: this is the surface where the extraction admits it could
 * not reduce a price to a number, and where a document-sourced offering finally
 * carries a description at all.
 */
function candidate(overrides: Partial<ReviewOffering> = {}): ReviewOffering {
  return {
    name: "Bowl",
    description: "",
    price_cents: null,
    sources: ["document"],
    ...overrides,
  };
}

describe("toWorkingOffering", () => {
  it("shows a description extracted from a document", () => {
    // The predecessor never populated `description` from a document at all -
    // every document-sourced row arrived blank and had to be typed by hand.
    const working = toWorkingOffering(
      candidate({ description: "comes with pita on the side", price_cents: 2700 }),
    );
    expect(working.description).toBe("comes with pita on the side");
    expect(working.priceText).toBe("$27.00");
  });

  it("shows the source's own wording for a price it refused to flatten", () => {
    const working = toWorkingOffering(
      candidate({ name: "Plate", needs_review: true, price_note: "both run $20–$30" }),
    );
    expect(working.priceText).toBe("");
    expect(working.priceNote).toBe("both run $20–$30");
  });

  it("does not treat a missing price as something to check", () => {
    // A source is allowed to be silent about what something costs. Flagging
    // that would put a warning on most of a real menu.
    const working = toWorkingOffering(candidate({ name: "chicken shawarma" }));
    expect(working.priceNote).toBe("");
    expect(working.priceText).toBe("");
  });

  it("carries possible matches without acting on them", () => {
    // Merging on similarity would silently delete a real offering, so the row
    // only ever points at its twin.
    const working = toWorkingOffering(
      candidate({ name: "coffe", possible_matches: ["coffee drinks"] }),
    );
    expect(working.possibleMatches).toEqual(["coffee drinks"]);
    expect(working.name).toBe("coffe");
  });

  it("defaults every new field so an owner-typed offering still works", () => {
    const working = toWorkingOffering({
      name: "Screen repair",
      description: "",
      price_cents: 8900,
      sources: ["owner"],
    });
    expect(working).toMatchObject({
      priceNote: "",
      possibleMatches: [],
      priceOptions: [],
      support_state: "supported",
      dirty: false,
    });
  });

  it("passes W-11 supporting document ids and support state through", () => {
    const working = toWorkingOffering(
      candidate({
        supporting_document_ids: ["doc-1"],
        support_state: "orphaned",
      }),
    );
    expect(working.supporting_document_ids).toEqual(["doc-1"]);
    expect(working.support_state).toBe("orphaned");
    expect(working.dirty).toBe(false);
  });
});

describe("offering pagination", () => {
  it.each([
    [0, 1],
    [5, 1],
    [6, 2],
    [40, 8],
    [51, 11],
  ])("uses five offerings per page for %i offerings", (count, pages) => {
    expect(offeringPageCount(count)).toBe(pages);
  });

  it("keeps the sixth offering on its own editor page", () => {
    const offerings = Array.from({ length: 6 }, (_, index) => `offering-${index + 1}`);
    expect(offeringPage(offerings, 0)).toEqual(offerings.slice(0, 5));
    expect(offeringPage(offerings, 1)).toEqual(["offering-6"]);
    expect(pageForOffering(5)).toBe(1);
  });
});

describe("review toolbar", () => {
  function record(overrides: Partial<KnowledgeRecord> = {}): KnowledgeRecord {
    return {
      id: "doc-1",
      filename: "menu.pdf",
      doc_type: "other",
      status: "draft",
      error: null,
      sections: [],
      ...overrides,
    };
  }

  function workspaceWith(offeringCount: number, priceCents: number | null = 1000): ReviewWorkspace {
    return {
      id: "ws-1",
      documents: [record()],
      offering_candidates: Array.from({ length: offeringCount }, (_, index) => ({
        name: `Offering ${index + 1}`,
        description: "",
        price_cents: priceCents,
        sources: ["owner"] as const,
      })),
    };
  }

  function renderSheet(workspace: ReviewWorkspace): string {
    return renderToStaticMarkup(
      <ReviewSheet
        workspace={workspace}
        open
        busy={false}
        priceConflict={null}
        onClose={() => {}}
        onSave={async () => null}
        onDiscard={() => {}}
      />,
    );
  }

  it("puts Review all and Add offering below the last collapsed card", () => {
    const html = renderSheet(workspaceWith(7));
    expect(html).toContain('<div class="mt-3 flex items-center justify-between">');
    expect(html).toContain("Review all 7 offerings");
    expect(html).toContain(">Add offering</button>");
    // Collapsed on the mobile/SSR render: three cards, the rest hidden,
    // pagination stays hidden.
    for (const name of ["Offering 1", "Offering 2", "Offering 3"]) {
      expect(html).toContain(`>${name}</h4>`);
    }
    for (const name of ["Offering 4", "Offering 5", "Offering 6"]) {
      expect(html).not.toContain(`>${name}</h4>`);
    }
    const lastCard = html.indexOf(">Offering 3</h4>");
    expect(html.indexOf("Review all 7 offerings")).toBeGreaterThan(lastCard);
    expect(html.indexOf(">Add offering</button>")).toBeGreaterThan(lastCard);
    expect(html).not.toContain("Page 1 of");
  });

  it("shows Review all when the catalog exceeds the mobile cap", () => {
    const html = renderSheet(workspaceWith(4));
    expect(html).toContain("Review all 4 offerings");
    expect(html).not.toContain(">Offering 4</h4>");
  });

  it("right-aligns Add offering with an empty span when Review all is hidden", () => {
    const html = renderSheet(workspaceWith(2));
    expect(html).not.toContain("Review all");
    // The press feedback lives on the button, not in an exact class string:
    // hover underline plus the label, with the empty span keeping it right.
    expect(html).toContain("hover:underline");
    expect(html).toContain(">Add offering</button>");
    // Inside the cap the rows are editable, so the cards render inputs rather
    // than headings - anchor on the last article instead.
    const lastCard = html.lastIndexOf("<article");
    const span = html.indexOf("<span></span>");
    expect(span).toBeGreaterThan(lastCard);
    expect(span).toBeLessThan(html.indexOf(">Add offering</button>"));
    expect(html.indexOf(">Add offering</button>")).toBeGreaterThan(lastCard);
  });

  it("inserts a new offering after the last owner row and pages to it", () => {
    const owners = Array.from({ length: 11 }, (_, index) =>
      toWorkingOffering({
        name: `Owner ${index + 1}`,
        description: "",
        price_cents: null,
        sources: ["owner"],
      }),
    );
    const imported = toWorkingOffering({
      name: "Imported",
      description: "",
      price_cents: null,
      sources: ["document"],
    });
    const fresh = toWorkingOffering({
      name: "Fresh",
      description: "",
      price_cents: null,
      sources: ["owner"],
    });
    const after = insertOwnerOffering([...owners, imported], fresh);
    expect(after.list.map((item) => item.name)).toEqual([
      ...owners.map((item) => item.name),
      "Fresh",
      "Imported",
    ]);
    expect(after.page).toBe(pageForOffering(11));
    // No owner rows: the fresh row leads the list on page 1.
    const top = insertOwnerOffering([imported], fresh);
    expect(top.list.map((item) => item.name)).toEqual(["Fresh", "Imported"]);
    expect(top.page).toBe(0);
  });
});

describe("suggestions-only review", () => {
  /**
   * The suggestions sheet is the only place a private draft is ever shown. It
   * shares the sheet and the offering card with the knowledge review, but it
   * reviews candidates alone - there is no document, no workspace, and nothing
   * to publish until the owner saves. (The save itself is a click, so the
   * approved payload is asserted in the e2e spec, not here.)
   */
  function suggestion(name: string, overrides: Partial<ReviewOffering> = {}): ReviewOffering {
    return {
      candidate_id: `cand-${name.toLowerCase().replace(/\s+/g, "-")}`,
      name,
      description: "",
      price_cents: null,
      sources: ["document"],
      review_status: "pending",
      ...overrides,
    };
  }

  function renderSuggestions(suggestions: ReviewOffering[], withHandler = true): string {
    return renderToStaticMarkup(
      <ReviewSheet
        workspace={null}
        suggestions={suggestions}
        suggestionsOnly
        open
        busy={false}
        priceConflict={null}
        onClose={() => {}}
        onSave={async () => null}
        onSaveSuggestions={withHandler ? async () => {} : undefined}
        onDiscard={() => {}}
      />,
    );
  }

  it("puts every candidate in a row the owner can edit before approving", () => {
    const html = renderSuggestions([suggestion("Screen repair"), suggestion("Battery swap")]);
    expect(html).toContain("Suggestions to review");
    expect(html).toContain('value="Screen repair"');
    expect(html).toContain('value="Battery swap"');
    expect(html).toContain('data-testid="suggestions-save"');
  });

  it("says outright that nothing here has reached a customer", () => {
    // The owner is being asked to approve drafts the assistant wrote from
    // their own uploads. Whether those are already live is the first thing
    // they need to know, so it is stated on the sheet rather than implied.
    const html = renderSuggestions([suggestion("Screen repair")]);
    expect(html).toContain("These private drafts never reach customers until you save them.");
  });

  it("renders nothing to review without a handler to save through", () => {
    // A sheet with a Save button that goes nowhere is worse than no sheet.
    const html = renderSuggestions([suggestion("Screen repair")], false);
    expect(html).not.toContain('value="Screen repair"');
    expect(html).not.toContain('data-testid="suggestions-save"');
  });
});

describe("review field recipe (31)", () => {
  function renderEditable(): string {
    const workspace: ReviewWorkspace = {
      id: "ws-1",
      documents: [
        {
          id: "doc-1",
          filename: "menu.pdf",
          doc_type: "other",
          status: "draft",
          error: null,
          sections: [],
        },
      ],
      offering_candidates: [
        {
          candidate_id: "c-1",
          name: "Bowl",
          description: "comes with pita",
          price_cents: 1200,
          sources: ["owner"],
        },
      ],
    };
    return renderToStaticMarkup(
      <ReviewSheet
        workspace={workspace}
        open
        busy={false}
        priceConflict={null}
        onClose={() => {}}
        onSave={async () => null}
        onDiscard={() => {}}
      />,
    );
  }

  it("gives every review field the shared field recipe", () => {
    const html = renderEditable();
    expect(html).toContain("min-h-11");
    expect(html).toContain("px-4 py-3 text-body");
    expect(html).not.toContain("text-field");
  });

  it("widens the price field to the 96px step", () => {
    const html = renderEditable();
    expect(html).toContain('class="w-24 rounded-field');
    expect(html).not.toContain("w-28");
  });
});

describe("collapsed categories (31)", () => {
  function renderCard(overrides: Partial<ReviewOffering> = {}): string {
    const workspace: ReviewWorkspace = {
      id: "ws-1",
      documents: [
        {
          id: "doc-1",
          filename: "menu.pdf",
          doc_type: "other",
          status: "draft",
          error: null,
          sections: [],
        },
      ],
      offering_candidates: [
        {
          candidate_id: "c-1",
          name: "Bowl",
          description: "",
          price_cents: 1200,
          sources: ["owner"],
          ...overrides,
        },
      ],
    };
    return renderToStaticMarkup(
      <ReviewSheet
        workspace={workspace}
        open
        busy={false}
        priceConflict={null}
        onClose={() => {}}
        onSave={async () => null}
        onDiscard={() => {}}
      />,
    );
  }

  it("keeps a card with no category collapsed behind one trigger", () => {
    const html = renderCard();
    expect(html).toContain('data-testid="review-category-trigger"');
    expect(html).toContain(">Add category</button>");
    expect(html).toContain('aria-expanded="false"');
    // Closed means the picker is not in the DOM at all, not merely hidden.
    expect(html).not.toContain("Search or create a category");
  });

  it("labels a card that already has categories by its count", () => {
    const html = renderCard({ category_ids: ["a", "b"], primary_category_id: "a" });
    expect(html).toContain(">Categories (2)</button>");
    expect(html).toContain('aria-expanded="false"');
  });

  it("keeps the suggested category out of the collapsed card", () => {
    // 31: the line moved inside the expanded region, so a closed card is one
    // row shorter than the ticket-29 render.
    const html = renderCard({ proposed_category: "Coffee" });
    expect(html).not.toContain("Suggested category");
  });
});

describe("removal confirmations (31)", () => {
  it("pins the offering removal copy, tone and layer", () => {
    expect(removeOfferingConfirm("Screen repair")).toEqual({
      title: "Remove Screen repair?",
      description: "It will not be saved to your catalog.",
      confirmLabel: "Remove",
      tone: "danger",
      layer: "top",
    });
  });

  it("names one source or several when the footer discard is used", () => {
    expect(discardConfirm(1)).toMatchObject({
      title: "Discard this source?",
      description: "It is deleted, and its details and offerings are not saved.",
      confirmLabel: "Discard source",
      tone: "danger",
      layer: "top",
    });
    expect(discardConfirm(2)).toMatchObject({
      title: "Discard these sources?",
      description: "They are deleted, and their details and offerings are not saved.",
      confirmLabel: "Discard sources",
      tone: "danger",
      layer: "top",
    });
  });

  it("labels the onboarding footer by the number of reviewed sources", () => {
    const one = renderToStaticMarkup(
      <ReviewSheet
        workspace={{
          id: "ws-1",
          documents: [
            {
              id: "doc-1",
              filename: "menu.pdf",
              doc_type: "other",
              status: "draft",
              error: null,
              sections: [],
            },
          ],
          offering_candidates: [],
        }}
        onboarding
        open
        busy={false}
        priceConflict={null}
        onClose={() => {}}
        onSave={async () => null}
        onDiscard={() => {}}
      />,
    );
    expect(one).toContain(">Discard source</button>");

    const two = renderToStaticMarkup(
      <ReviewSheet
        workspace={{
          id: "ws-1",
          documents: [
            {
              id: "doc-1",
              filename: "menu.pdf",
              doc_type: "other",
              status: "draft",
              error: null,
              sections: [],
            },
            {
              id: "doc-2",
              filename: "hours.pdf",
              doc_type: "other",
              status: "draft",
              error: null,
              sections: [],
            },
          ],
          offering_candidates: [],
        }}
        onboarding
        open
        busy={false}
        priceConflict={null}
        onClose={() => {}}
        onSave={async () => null}
        onDiscard={() => {}}
      />,
    );
    expect(two).toContain(">Discard sources</button>");
  });
});

describe("suggestions pagination (31)", () => {
  function nineSuggestions(): ReviewOffering[] {
    return Array.from({ length: 9 }, (_, index) => ({
      candidate_id: `cand-${index + 1}`,
      name: `Suggestion ${index + 1}`,
      description: "",
      price_cents: null,
      sources: ["document"] as const,
      review_status: "pending" as const,
    }));
  }

  function renderNine(): string {
    return renderToStaticMarkup(
      <ReviewSheet
        workspace={null}
        suggestions={nineSuggestions()}
        suggestionsOnly
        open
        busy={false}
        priceConflict={null}
        onClose={() => {}}
        onSave={async () => null}
        onSaveSuggestions={async () => {}}
        onDiscard={() => {}}
      />,
    );
  }

  function renderedNames(html: string): number {
    return (html.match(/aria-label="Offering \d+ name"/g) ?? []).length;
  }

  it("shows five suggestions a page on the desktop branch", () => {
    vi.mocked(useMediaQuery).mockReturnValue(true);
    const html = renderNine();
    expect(renderedNames(html)).toBe(5);
    expect(html).toContain("Page 1 of 2");
    expect(html).toContain("Showing 1-5 of 9 suggestions");
  });

  it("shows three suggestions a page on the phone branch", () => {
    const html = renderNine();
    expect(renderedNames(html)).toBe(3);
    expect(html).toContain("Page 1 of 3");
    expect(html).toContain("Showing 1-3 of 9 suggestions");
  });

  it("keeps the review's own pagination copy by default", () => {
    // 31: pageSize and noun are opt-in; the review's five-a-page offerings
    // wording is unchanged.
    const html = renderToStaticMarkup(
      <Pagination page={0} pages={2} count={9} onPage={() => {}} />,
    );
    expect(html).toContain("Showing 1-5 of 9 offerings");
  });
});

describe("pagination copy", () => {
  function renderPagination(page: number, pages: number, count: number): string {
    return renderToStaticMarkup(
      <Pagination page={page} pages={pages} count={count} onPage={() => {}} />,
    );
  }

  it("says Page X of Y and Showing A-B of N offerings", () => {
    const first = renderPagination(0, 3, 12);
    expect(first).toContain("Page 1 of 3");
    expect(first).toContain("Showing 1-5 of 12 offerings");
    expect(first).toContain('disabled=""');
    const middle = renderPagination(1, 3, 12);
    expect(middle).toContain("Page 2 of 3");
    expect(middle).toContain("Showing 6-10 of 12 offerings");
    const last = renderPagination(2, 3, 12);
    expect(last).toContain("Page 3 of 3");
    expect(last).toContain("Showing 11-12 of 12 offerings");
  });

  it("always says offerings, even for a single row on the last page", () => {
    const html = renderPagination(1, 2, 6);
    expect(html).toContain("Showing 6-6 of 6 offerings");
  });

  it("disables Previous on the first page and Next on the last", () => {
    const first = renderPagination(0, 3, 12);
    expect(first).toMatch(/<button type="button" disabled=""[^>]*>Previous<\/button>/);
    expect(first).not.toMatch(/<button type="button" disabled=""[^>]*>Next<\/button>/);
    const last = renderPagination(2, 3, 12);
    expect(last).not.toMatch(/<button type="button" disabled=""[^>]*>Previous<\/button>/);
    expect(last).toMatch(/<button type="button" disabled=""[^>]*>Next<\/button>/);
  });
});

describe("review workspace clarity", () => {
  function record(overrides: Partial<KnowledgeRecord> = {}): KnowledgeRecord {
    return {
      id: "doc-1",
      filename: "menu.pdf",
      doc_type: "other",
      status: "draft",
      error: null,
      sections: [{ heading: "Hours", body: "9 to 5" }],
      ...overrides,
    };
  }

  function workspace(status: string): ReviewWorkspace {
    return {
      id: "ws-1",
      documents: [record({ status })],
      offering_candidates: [
        { candidate_id: "c-1", name: "Bowl", description: "", price_cents: null, sources: ["document"] },
      ],
    };
  }

  function renderClarity(
    sheet: ReviewWorkspace,
    onboarding = false,
    profile?: ReviewProfile,
  ): string {
    return renderToStaticMarkup(
      <ReviewSheet
        workspace={sheet}
        onboarding={onboarding}
        profile={profile}
        open
        busy={false}
        priceConflict={null}
        onClose={() => {}}
        onSave={async () => null}
        onDiscard={() => {}}
      />,
    );
  }

  it("names the footer secondary by context: draft, saved, and onboarding", () => {
    // Onboarding discards a private draft; business mode is explicit that a
    // draft is discarded and a saved source is removed.
    expect(renderClarity(workspace("draft"))).toContain(">Discard draft</button>");
    expect(renderClarity(workspace("ready"))).toContain(">Remove source</button>");
    expect(renderClarity(workspace("draft"), true)).toContain(">Discard source</button>");
  });

  it("renders the sections in DOM order matching the visual order", () => {
    // 29: the review leads with what the business offers, then the business
    // details the source found, then the source line.
    const business = renderClarity(workspace("draft"));
    expect(business.indexOf("What you offer")).toBeLessThan(business.indexOf("Sources"));
    const onboarding = renderClarity(workspace("draft"), true, {
      business_name: "Test Repairs",
    });
    expect(onboarding.indexOf("What you offer")).toBeLessThan(
      onboarding.indexOf("Business details"),
    );
    expect(onboarding.indexOf("Business details")).toBeLessThan(
      onboarding.indexOf("Sources"),
    );
  });

  it("drops the repeated source line from the business offerings count", () => {
    // The intro already names the source, so the count must not repeat it.
    const business = renderClarity(workspace("draft"));
    expect(business).toMatch(/<p class="mt-1 text-meta text-ink-a40">1 retained offering/);
    expect(business).not.toMatch(/<p class="mt-1 text-meta text-ink-a40">From /);
  });
});

describe("priced-first review (29)", () => {
  function record(overrides: Partial<KnowledgeRecord> = {}): KnowledgeRecord {
    return {
      id: "doc-1",
      filename: "menu.pdf",
      doc_type: "other",
      status: "draft",
      error: null,
      sections: [{ heading: "Hours", body: "The secret document body" }],
      ...overrides,
    };
  }

  function renderPricedFirst({
    offerings = [candidate({ candidate_id: "c1", name: "Bowl" })],
    profile,
    missingRequired,
    sectionBody = "The secret document body",
  }: {
    offerings?: ReviewOffering[];
    profile?: ReviewProfile;
    missingRequired?: string[];
    sectionBody?: string;
  } = {}): string {
    const workspace: ReviewWorkspace = {
      id: "ws-1",
      documents: [
        record({
          sections: [{ heading: "Hours", body: sectionBody }],
        }),
      ],
      offering_candidates: offerings,
    };
    return renderToStaticMarkup(
      <ReviewSheet
        workspace={workspace}
        open
        busy={false}
        priceConflict={null}
        profile={profile}
        missingRequired={missingRequired}
        onClose={() => {}}
        onSave={async () => null}
        onDiscard={() => {}}
      />,
    );
  }

  it("opens expanded with the banner when a service has no price", () => {
    const offerings = Array.from({ length: 7 }, (_, index) =>
      candidate({
        candidate_id: `c${index}`,
        name: `Offering ${index + 1}`,
        price_cents: index === 6 ? null : 1000,
      }),
    );

    const html = renderPricedFirst({ offerings });

    expect(html).toContain(
      "No prices found here. Add a price, or write it your way, like &quot;from $30&quot;.",
    );
    // The server render is the mobile/SSR three-row cap; the fourth row is only
    // present when the list opened expanded.
    expect(html).toContain('aria-label="Offering 4 name"');
  });

  it("keeps the banner away when every service has a price", () => {
    const html = renderPricedFirst({
      offerings: [candidate({ name: "Bowl", price_cents: 1200 })],
    });

    expect(html).not.toContain("No prices found here.");
  });

  it("serialises a number to price_cents and words to pricing_wording, never both", () => {
    const numeric = toPendingOffering(
      toWorkingOffering(candidate({ price_cents: 4500 })),
    );
    const worded = toPendingOffering(
      toWorkingOffering(candidate({ price_cents: null, pricing_wording: "from $30" })),
    );
    const empty = toPendingOffering(
      toWorkingOffering(candidate({ price_cents: null })),
    );

    expect(numeric.price_cents).toBe(4500);
    expect(numeric.pricing_wording).toBe("");
    expect(worded.price_cents).toBeNull();
    expect(worded.pricing_wording).toBe("from $30");
    expect(empty.price_cents).toBeNull();
    expect(empty.pricing_wording).toBe("");
    for (const payload of [numeric, worded, empty]) {
      expect(Boolean(payload.price_cents != null && payload.pricing_wording)).toBe(false);
    }
  });

  it("clears the server's conflicting wordings when the owner edits the price", () => {
    expect(priceInputUpdate("$30").wording_options).toEqual([]);
    expect(priceInputUpdate("from $30").wording_options).toEqual([]);
  });

  it("keeps the server's conflicting wordings on a save so the gate still sees them", () => {
    const payload = toPendingOffering(
      toWorkingOffering(
        candidate({
          price_cents: null,
          pricing_wording: "from $30",
          wording_options: ["from $30", "market price"],
        }),
      ),
    );

    expect(payload.wording_options).toEqual(["from $30", "market price"]);
  });

  it("patches only the profile rows the owner changed", () => {
    // The state draft also carries lists (services); a string patch must never
    // try to trim one, and a displayed value is not an edit.
    expect(
      profilePatchFor(
        {
          business_name: "Bytefix",
          services: ["Screen repair"],
          hours: "Mon-Fri 9-6",
        },
        { business_name: "Bytefix" },
      ),
    ).toEqual({ hours: "Mon-Fri 9-6" });
  });

  it("renders the ABN row only when the source found one", () => {
    const withAbn = renderPricedFirst({
      profile: { business_name: "Bytefix", abn: "51824753556" },
    });
    expect(withAbn).toContain('data-testid="review-profile-abn"');

    const without = renderPricedFirst({
      profile: { business_name: "Bytefix" },
    });
    expect(without).not.toContain('data-testid="review-profile-abn"');
  });

  it("lists the required beats the source left empty in one note", () => {
    const html = renderPricedFirst({
      profile: { business_name: "Bytefix" },
      missingRequired: ["business type", "what you offer", "contact details"],
    });

    expect(html).toContain(
      "I&#x27;ll ask next: business type, what you offer, contact details.",
    );
  });

  it("does not render empty required rows", () => {
    const html = renderPricedFirst({
      profile: { business_name: "Bytefix" },
    });

    expect(html).toContain('data-testid="review-profile-business_name"');
    expect(html).not.toContain('data-testid="review-profile-business_type"');
    expect(html).not.toContain('data-testid="review-profile-hours"');
    expect(html).not.toContain('data-testid="review-profile-contact"');
  });

  it("keeps the structured sections behind a closed disclosure by default", () => {
    const html = renderPricedFirst({ sectionBody: "The secret document body" });

    expect(html).toContain("More about what I read");
    expect(html).not.toContain("The secret document body");
    expect(html).not.toContain("Original extracted source");
  });
});

describe("link editing (31)", () => {
  function record(overrides: Partial<KnowledgeRecord> = {}): KnowledgeRecord {
    return {
      id: "doc-1",
      filename: "https://bytefix.example.com/menu",
      doc_type: "website",
      status: "draft",
      error: null,
      sections: [],
      ...overrides,
    };
  }

  function renderSources(
    documents: KnowledgeRecord[],
    handlers: {
      onReplaceLink?: (documentId: string, url: string) => Promise<{ record: KnowledgeRecord; draft: Record<string, unknown> } | null>;
      onAddLink?: (url: string) => Promise<KnowledgeRecord[]>;
      onAddSource?: (files: File[]) => Promise<KnowledgeRecord[]>;
      onReplaceSource?: (documentId: string, file: File) => Promise<KnowledgeRecord | null>;
      onRemoveSource?: (documentId: string) => Promise<void>;
    } = {},
  ): string {
    return renderToStaticMarkup(
      <ReviewSheet
        workspace={{ id: "ws-1", documents, offering_candidates: [] }}
        onboarding
        open
        busy={false}
        priceConflict={null}
        onClose={() => {}}
        onSave={async () => null}
        onDiscard={() => {}}
        {...handlers}
      />,
    );
  }

  const sourceHandlers = {
    onReplaceLink: async () => null,
    onAddLink: async () => [],
    onAddSource: async () => [],
    onReplaceSource: async () => null,
    onRemoveSource: async () => {},
  };

  it("pins the link replacement question", () => {
    expect(replaceLinkConfirm()).toEqual({
      title: "Replace this link?",
      description:
        "The new site will be read, and its details and offerings will replace this source.",
      confirmLabel: "Replace link",
      tone: "danger",
      layer: "top",
    });
  });

  it("gives a URL row an inline edit and keeps the file picker off it", () => {
    const html = renderSources([record()], sourceHandlers);
    expect(html).toContain('data-testid="review-edit-link"');
    expect(html).toContain('aria-label="Edit link for bytefix.example.com"');
    expect(html).toContain(">Edit link</button>");
    expect(html).not.toContain('data-testid="review-replace-source"');
    // Closed means the editor is not in the DOM at all.
    expect(html).not.toContain('data-testid="review-link-input"');
  });

  it("keeps the file picker on a file row and offers no link edit", () => {
    const html = renderSources([record({ doc_type: "other", filename: "menu.pdf" })], sourceHandlers);
    expect(html).toContain('data-testid="review-replace-source"');
    expect(html).not.toContain('data-testid="review-edit-link"');
  });

  it("offers add a link and add a file as two actions", () => {
    const html = renderSources([record({ doc_type: "other", filename: "menu.pdf" })], sourceHandlers);
    expect(html).toContain('data-testid="review-add-link"');
    expect(html).toContain(">Add a link</button>");
    expect(html).toContain('data-testid="review-add-file"');
    expect(html).toContain(">Add a file</button>");
    expect(html).not.toContain("Add another source");
  });

  it("renders no source actions on a surface that passes no handlers", () => {
    const html = renderSources([record()]);
    expect(html).not.toContain('data-testid="review-edit-link"');
    expect(html).not.toContain('data-testid="review-add-link"');
    expect(html).not.toContain('data-testid="review-add-file"');
    expect(html).not.toContain('data-testid="review-remove-source"');
  });

  it("keeps a same-URL re-read in place, so every row keeps its source", () => {
    // Replacing a link with the same address re-reads the same document row.
    // Reconciling that row against itself would strip the id that names its
    // source, so the re-read merges in place instead.
    const document = record();
    const previous: ReviewOffering[] = [
      candidate({
        candidate_id: "c-1",
        name: "Screen repairs",
        sources: ["document"],
        supporting_document_ids: ["doc-1"],
      }),
      candidate({
        candidate_id: "c-2",
        name: "Screen protectors",
        sources: ["owner", "document"],
        supporting_document_ids: ["doc-1"],
        support_state: "supported",
      }),
    ];
    const reRead = record({
      offering_candidates: [
        candidate({ name: "Screen repairs", sources: ["document"], supporting_document_ids: ["doc-1"] }),
        candidate({ name: "battery replacements", sources: ["document"], supporting_document_ids: ["doc-1"] }),
      ],
    });

    const next = reconcileLinkOfferings(previous, reRead, "doc-1", new Set(["c-2"]));

    expect(next.map((item) => item.name)).toEqual([
      "Screen repairs",
      "Screen protectors",
      "battery replacements",
    ]);
    // The row the page added on the re-read still resolves to its source.
    const added = next.find((item) => item.name === "battery replacements");
    expect(added?.supporting_document_ids).toContain("doc-1");
    expect(offeringLabel(added!, [document])).toBe("From bytefix.example.com");
    // The row the owner edited survives, still backed by the source it names.
    const edited = next.find((item) => item.name === "Screen protectors");
    expect(edited?.supporting_document_ids).toContain("doc-1");
    expect(edited?.sources).toEqual(["owner", "document"]);
    expect(edited?.support_state).toBe("supported");
  });

  it("drops an unedited row when a different URL replaces the source", () => {
    const previous: ReviewOffering[] = [
      candidate({
        candidate_id: "c-1",
        name: "Screen repairs",
        sources: ["document"],
        supporting_document_ids: ["doc-1"],
      }),
      candidate({ candidate_id: "c-2", name: "Owner typed row", sources: ["owner"] }),
    ];
    const replacement = record({
      id: "doc-2",
      filename: "https://new.example.com",
      offering_candidates: [
        candidate({ name: "Battery replacements", sources: ["document"], supporting_document_ids: ["doc-2"] }),
      ],
    });

    const next = reconcileLinkOfferings(previous, replacement, "doc-1", new Set());

    // Nothing else vouches for the old document's row; the owner's own row stays.
    expect(next.map((item) => item.name)).toEqual(["Owner typed row", "Battery replacements"]);
  });
});
