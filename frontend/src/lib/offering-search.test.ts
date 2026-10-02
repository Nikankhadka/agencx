import { describe, expect, it } from "vitest";
import { filterOfferings } from "./offering-search";

function offering(overrides: Record<string, unknown>) {
  return {
    id: "1",
    name: "Item",
    description: "",
    category: null as string | null,
    categories: [] as Array<{ name: string }>,
    ...overrides,
  };
}

describe("filterOfferings", () => {
  const items = [
    offering({ id: "a", name: "Iced coffee", description: "Served over ice" }),
    offering({
      id: "b",
      name: "Lemonade",
      category: "Cold drinks",
      categories: [{ name: "Cold drinks" }],
    }),
    offering({ id: "c", name: "Hot chocolate", description: "With whipped cream" }),
  ];

  it("matches the name, case-insensitively", () => {
    expect(filterOfferings(items, "iced").map((item) => item.id)).toEqual(["a"]);
    expect(filterOfferings(items, "COFFEE").map((item) => item.id)).toEqual(["a"]);
  });

  it("matches the description", () => {
    expect(filterOfferings(items, "whipped").map((item) => item.id)).toEqual(["c"]);
  });

  it("matches a category name", () => {
    expect(filterOfferings(items, "cold").map((item) => item.id)).toEqual(["b"]);
  });

  it("returns every offering for an empty query", () => {
    expect(filterOfferings(items, "")).toEqual(items);
    expect(filterOfferings(items, "   ")).toEqual(items);
  });

  it("treats a wildcard character literally", () => {
    expect(filterOfferings(items, "%")).toEqual([]);
  });
});
