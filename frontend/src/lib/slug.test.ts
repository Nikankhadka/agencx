import { describe, expect, it } from "vitest";
import { slugShapeError } from "./slug";

describe("slugShapeError", () => {
  it("accepts valid slugs", () => {
    for (const value of ["abc", "bytefix-repairs", "a1-b2-c3", "x".repeat(40)]) {
      expect(slugShapeError(value)).toBeNull();
    }
  });

  it("names the fix for an empty field without reciting a regex", () => {
    const message = slugShapeError("");
    expect(message).toBe("Enter a page address.");
  });

  it("rejects a slug shorter than 3 characters", () => {
    expect(slugShapeError("ab")).toContain("at least 3");
  });

  it("rejects a slug longer than 40 characters", () => {
    expect(slugShapeError("x".repeat(41))).toContain("40");
  });

  it("rejects a leading dash", () => {
    expect(slugShapeError("-abc")).not.toBeNull();
  });

  it("rejects a trailing dash", () => {
    expect(slugShapeError("abc-")).not.toBeNull();
  });

  it("rejects a double dash", () => {
    expect(slugShapeError("ab--cd")).not.toBeNull();
  });

  it("rejects uppercase letters", () => {
    expect(slugShapeError("ABC")).not.toBeNull();
  });

  it("rejects spaces", () => {
    expect(slugShapeError("ab cd")).not.toBeNull();
  });

  it("rejects unicode characters", () => {
    expect(slugShapeError("café-shop")).not.toBeNull();
  });

  it("does not reject a reserved name - that check belongs to the server", () => {
    expect(slugShapeError("settings")).toBeNull();
    expect(slugShapeError("admin")).toBeNull();
  });
});
