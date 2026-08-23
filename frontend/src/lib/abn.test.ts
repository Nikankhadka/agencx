import { describe, expect, it } from "vitest";
import { abnSummary, formatAbn, isGstRegistered } from "./abn";

describe("formatAbn", () => {
  it("groups eleven digits the way the prototype does", () => {
    expect(formatAbn("51824753556")).toBe("51 824 753 556");
  });

  it("groups as the owner types", () => {
    expect(formatAbn("5")).toBe("5");
    expect(formatAbn("518")).toBe("51 8");
    expect(formatAbn("518247")).toBe("51 824 7");
  });

  it("is idempotent on an already formatted value", () => {
    expect(formatAbn("51 824 753 556")).toBe("51 824 753 556");
  });

  it("drops anything past eleven digits", () => {
    expect(formatAbn("5182475355612345")).toBe("51 824 753 556");
  });
});

describe("isGstRegistered", () => {
  it("reads what the interview stores", () => {
    expect(isGstRegistered("yes")).toBe(true);
    expect(isGstRegistered("no")).toBe(false);
  });

  it("reads the chip labels it was extracted from", () => {
    expect(isGstRegistered("Yes")).toBe(true);
    expect(isGstRegistered("Not yet")).toBe(false);
  });

  it("treats nothing captured as not registered", () => {
    expect(isGstRegistered("")).toBe(false);
  });
});

describe("abnSummary", () => {
  it("reads back the number and the GST answer", () => {
    expect(abnSummary({ abn: "51824753556", gst: "yes" })).toBe(
      "51 824 753 556 · GST registered",
    );
    expect(abnSummary({ abn: "51824753556", gst: "no" })).toBe(
      "51 824 753 556 · Not GST registered",
    );
  });

  it("does not answer a GST question an owner without an ABN never heard", () => {
    expect(abnSummary({ abn: "none", gst: "" })).toBe("No ABN");
  });

  it("says so when nothing was captured", () => {
    expect(abnSummary({ abn: "", gst: "" })).toBe("Not set");
  });
});
