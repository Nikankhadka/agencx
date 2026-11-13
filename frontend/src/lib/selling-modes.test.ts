import { describe, expect, it } from "vitest";
import {
  buildSellingModePayload,
  confirmationCopy,
  LABEL_DEFAULTS,
  labelFor,
  labelsFor,
  mergedCapabilities,
  MODE_PRESETS,
  rowsFor,
  type SellingModeSuggestion,
} from "./selling-modes";

/**
 * 32 slice A: the selling-mode card's pure logic.
 *
 * The backend is authoritative for the inference, the summary, and the stored
 * config; this module owns only what the client has to decide - which sentence
 * to show, which labels to render, and what a multi-select sends back. Its label
 * defaults are the backend's own map, mirrored, so the two are pinned here.
 */

function suggestion(overrides: Partial<SellingModeSuggestion> = {}): SellingModeSuggestion {
  const preset = MODE_PRESETS.orders;
  return {
    mode: "orders",
    capabilities: preset.capabilities,
    labels: preset.labels,
    defaults: { lead_time_minutes: 30 },
    confidence: "high",
    candidates: ["orders"],
    evidence: ['"menu" in your website'],
    summary: "Your assistant will take orders from your menu. You can change this later.",
    ...overrides,
  };
}

describe("confirmationCopy", () => {
  it("confirms a high-confidence guess in the owner's words", () => {
    const copy = confirmationCopy(suggestion());
    expect(copy.headline).toBe("It looks like customers order from you.");
    expect(copy.confirm).toBe("Yes, that's right");
    expect(copy.change).toBe("Change something");
    expect(copy.choices).toEqual([]);
  });

  it("asks which of two modes is primary when the source is ambiguous", () => {
    const copy = confirmationCopy(
      suggestion({ mode: "orders", confidence: "medium", candidates: ["orders", "bookings"] }),
    );
    expect(copy.headline).toBe(
      "It looks like customers either order from you or book with you. Which is closer?",
    );
    expect(copy.choices).toEqual(["orders", "bookings"]);
  });

  it("offers all four modes when there was no source to read", () => {
    const copy = confirmationCopy(
      suggestion({
        confidence: "low",
        candidates: ["orders", "bookings", "quotes", "products"],
      }),
    );
    expect(copy.headline).toBe("How do customers buy from you? Pick the closest.");
    expect(copy.choices).toEqual(["orders", "bookings", "quotes", "products"]);
    // A low-confidence guess is never offered as a one-tap yes.
    expect(copy.confirm).toBeNull();
  });
});

describe("labels", () => {
  it("falls back to the neutral default when a stored map omits a key", () => {
    expect(labelFor({ items: "Treatments" }, "items")).toBe("Treatments");
    expect(labelFor({ items: "Treatments" }, "item")).toBe("Item");
    expect(labelFor(undefined, "work")).toBe("Work");
  });

  it("mirrors the backend's default map", () => {
    expect(LABEL_DEFAULTS).toEqual({
      item: "Item",
      items: "Items",
      work: "Work",
      add_item: "Add item",
      time: "Time",
      sold_out: "Unavailable",
      action: "Action",
    });
  });

  it("drops an unknown label key instead of rendering it", () => {
    const labels = labelsFor(["orders"], { nonsense: "x", items: "Treatments" });
    expect(labels.items).toBe("Treatments");
    expect("nonsense" in labels).toBe(false);
    expect(Object.keys(labels).sort()).toEqual(Object.keys(LABEL_DEFAULTS).sort());
  });

  it("lets the first chosen mode own the wording", () => {
    expect(labelsFor(["bookings", "products"]).items).toBe("Services");
    expect(labelsFor(["products", "bookings"]).items).toBe("Products");
  });
});

describe("multi-select", () => {
  it("keeps every chosen mode and merges the bundles it implies", () => {
    const capabilities = mergedCapabilities(["orders", "products"]);
    expect(capabilities.sell).toEqual(["orders", "products"]);
    // A time promise beats no time promise, and a counted stock beats a flag.
    expect(capabilities.schedule).toBe("asap");
    expect(capabilities.stock).toBe("counted");
    expect(capabilities.fulfillment).toEqual(["in_house", "pickup", "shipping"]);
    expect(capabilities.acceptance).toBe("auto");
    expect(capabilities.payment).toBe("now");
  });

  it("builds the confirm payload the server validates", () => {
    const payload = buildSellingModePayload(["quotes"]);
    expect(payload.mode).toBe("quotes");
    expect(payload.capabilities.sell).toEqual(["quotes"]);
    expect(payload.labels.work).toBe("Requests");
  });

  it("takes a single axis edit without losing the rest of the bundle", () => {
    const payload = buildSellingModePayload(["bookings"], { stock: "flag" });
    expect(payload.capabilities.stock).toBe("flag");
    expect(payload.capabilities.schedule).toBe("slot");
  });

  it("sends an owner-set default only when there is one", () => {
    expect(buildSellingModePayload(["orders"]).defaults).toBeUndefined();
    expect(buildSellingModePayload(["orders"], {}, { lead_time_minutes: 45 }).defaults).toEqual({
      lead_time_minutes: 45,
    });
  });
});

describe("rowsFor", () => {
  it("asks only the follow-ups the picked mode has", () => {
    expect(rowsFor(["orders"])).toEqual([
      "fulfillment",
      "lead_time",
      "schedule",
      "stock",
      "payment",
    ]);
    expect(rowsFor(["bookings"])).toEqual(["schedule", "acceptance", "payment"]);
    expect(rowsFor(["quotes"])).toEqual(["schedule", "acceptance", "payment"]);
    expect(rowsFor(["products"])).toEqual(["fulfillment", "schedule", "stock", "payment"]);
  });

  it("unions two picked modes in one fixed order", () => {
    expect(rowsFor(["bookings", "orders"])).toEqual([
      "fulfillment",
      "lead_time",
      "schedule",
      "stock",
      "acceptance",
      "payment",
    ]);
  });

  it("never asks about approval in a mode that accepts automatically", () => {
    expect(rowsFor(["products"])).not.toContain("acceptance");
    expect(rowsFor(["bookings"])).not.toContain("lead_time");
  });
});
