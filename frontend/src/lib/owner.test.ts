import { describe, expect, it } from "vitest";
import { isStorefrontOwner } from "./owner";

describe("isStorefrontOwner", () => {
  it("matches when the viewer's own slug is the storefront slug", () => {
    expect(isStorefrontOwner("bytefix", "bytefix")).toBe(true);
  });

  it("does not match a different tenant's slug", () => {
    expect(isStorefrontOwner("lumident", "bytefix")).toBe(false);
  });

  it("never matches an anonymous viewer", () => {
    expect(isStorefrontOwner(null, "bytefix")).toBe(false);
    expect(isStorefrontOwner(undefined, "bytefix")).toBe(false);
  });
});
