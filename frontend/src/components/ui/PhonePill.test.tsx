import { describe, expect, it } from "vitest";
import { COUNTRIES } from "./PhonePill";

function country(code: string) {
  const found = COUNTRIES.find((entry) => entry.code === code);
  if (!found) throw new Error(`No country with dial code ${code}`);
  return found;
}

describe("PhonePill COUNTRIES", () => {
  it("formats and validates Nepali mobile numbers", () => {
    const nepal = country("+977");
    expect(nepal.format("9812345678")).toBe("9812 345 678");
    expect(nepal.format("98123")).toBe("9812 3");
    expect(nepal.format("98123456")).toBe("9812 345 6");
    expect(nepal.valid("9812345678")).toBe(true);
    expect(nepal.valid("9761234567")).toBe(true);
    expect(nepal.valid("9651234567")).toBe(true);
    expect(nepal.valid("9912345678")).toBe(true);
    expect(nepal.valid("981234567")).toBe(false);
    expect(nepal.valid("9512345678")).toBe(false);
  });

  it("formats and validates US numbers", () => {
    const us = country("+1");
    expect(us.format("5551234567")).toBe("(555) 123-4567");
    expect(us.format("5551234")).toBe("(555) 123-4");
    expect(us.format("555")).toBe("555");
    expect(us.valid("5551234567")).toBe(true);
    expect(us.valid("4155550132")).toBe(true);
    expect(us.valid("0551234567")).toBe(false);
    expect(us.valid("1551234567")).toBe(false);
    expect(us.valid("555123456")).toBe(false);
  });

  it("keeps Australian formatting and validation", () => {
    const au = country("+61");
    expect(au.format("0412345678")).toBe("0412 345 678");
    expect(au.valid("0412345678")).toBe(true);
    expect(au.valid("0212345678")).toBe(false);
  });
});
