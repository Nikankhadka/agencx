import { describe, expect, it } from "vitest";
import {
  COUNTRIES,
  countryByIso,
  filterCountries,
  normalizeStoredPhone,
  parseStoredPhone,
  resolveDefaultIso,
  toInternational,
} from "@/lib/phone";

function country(iso: string) {
  const found = countryByIso(iso);
  if (!found) throw new Error(`No country with ISO code ${iso}`);
  return found;
}

describe("PhonePill countries", () => {
  it("covers every libphonenumber region and keys them by ISO", () => {
    expect(COUNTRIES.length).toBeGreaterThanOrEqual(240);
    expect(new Set(COUNTRIES.map((entry) => entry.iso)).size).toBe(COUNTRIES.length);

    const australia = country("AU");
    expect(australia.name).toBe("Australia");
    expect(australia.code).toBe("+61");
    expect(australia.flag).toBe("🇦🇺");

    // A shared dial code is not a country: +1 covers the US, Canada and more.
    expect(country("US").code).toBe("+1");
    expect(country("CA").code).toBe("+1");
    expect(country("GB").code).toBe("+44");
    expect(country("NP").code).toBe("+977");
  });

  it("formats and validates a three-digit calling code", () => {
    const nepal = country("NP");
    expect(nepal.format("9812345678")).toBe("981-2345678");
    expect(nepal.format("98123")).toBe("981-23");
    expect(nepal.valid("9812345678")).toBe(true);
    expect(nepal.valid("9761234567")).toBe(true);
    expect(nepal.valid("981234567")).toBe(false);
    expect(nepal.valid("9512345678")).toBe(false);
  });

  it("formats and validates a one-digit calling code", () => {
    const us = country("US");
    expect(us.format("4155550132")).toBe("(415) 555-0132");
    expect(us.format("415")).toBe("(415)");
    expect(us.valid("4155550132")).toBe(true);
    expect(us.valid("0555555555")).toBe(false);
    expect(us.valid("1555555555")).toBe(false);
    expect(us.valid("415555013")).toBe(false);
  });

  it("formats and validates two-digit calling codes", () => {
    const uk = country("GB");
    expect(uk.format("07400123456")).toBe("07400 123456");
    expect(uk.valid("07400123456")).toBe(true);

    const germany = country("DE");
    expect(germany.format("15123456789")).toBe("15123456789");
    expect(germany.valid("15123456789")).toBe(true);

    const india = country("IN");
    expect(india.format("9876543210")).toBe("98765 43210");
    expect(india.valid("9876543210")).toBe(true);

    expect(country("JP").valid("9012345678")).toBe(true);
  });

  it("keeps Australian formatting and now accepts landlines", () => {
    const au = country("AU");
    expect(au.format("0412345678")).toBe("0412 345 678");
    expect(au.valid("0412345678")).toBe(true);
    // A business contact is often a landline; the old mobile-only rule was wrong.
    expect(au.valid("0212345678")).toBe(true);
    expect(au.valid("021234567")).toBe(false);
  });
});

describe("stored phone values", () => {
  it("emits international grouped values with the trunk prefix dropped", () => {
    expect(toInternational("0412345678", "AU")).toBe("+61 412 345 678");
    expect(toInternational("07400123456", "GB")).toBe("+44 7400 123456");
    expect(toInternational("", "GB")).toBe("+44");
  });

  it("decodes international and legacy values back into a country and national number", () => {
    const australia = parseStoredPhone("+61 412 345 678");
    expect(australia?.country.iso).toBe("AU");
    expect(australia?.local).toBe("0412 345 678");

    // The old widget stored the trunk zero after +61; it still opens correctly.
    const legacy = parseStoredPhone("+61 0412 345 678");
    expect(legacy?.country.iso).toBe("AU");
    expect(legacy?.local).toBe("0412 345 678");

    const canada = parseStoredPhone("+1 416 555 0132");
    expect(canada?.country.iso).toBe("CA");
    expect(canada?.local).toBe("(416) 555-0132");

    expect(parseStoredPhone("+44")?.country.iso).toBe("GB");
    expect(parseStoredPhone("+44")?.local).toBe("");

    // A national number typed into the free-text contact field is not a phone
    // with a region, but the fallback keeps it editable in the pill.
    expect(parseStoredPhone("0412 345 678", "AU")?.country.iso).toBe("AU");
  });

  it("returns null for anything that is not a phone number", () => {
    expect(parseStoredPhone("owner@bytefix.dev")).toBeNull();
    expect(parseStoredPhone("12 Main Street")).toBeNull();
    expect(parseStoredPhone("")).toBeNull();
  });

  it("normalizes a legacy stored value on save", () => {
    expect(normalizeStoredPhone("+61 0412 345 678")).toBe("+61 412 345 678");
    expect(normalizeStoredPhone("0412 345 678")).toBe("+61 412 345 678");
    expect(normalizeStoredPhone("owner@bytefix.dev")).toBe("owner@bytefix.dev");
    expect(normalizeStoredPhone("")).toBe("");
  });
});

describe("country defaults and search", () => {
  it("reads the region from the browser locale and falls back to AU", () => {
    expect(resolveDefaultIso(["en-AU"])).toBe("AU");
    expect(resolveDefaultIso(["de-DE"])).toBe("DE");
    expect(resolveDefaultIso(["sr-Latn-RS"])).toBe("RS");
    expect(resolveDefaultIso(["zh-Hant-TW"])).toBe("TW");
    expect(resolveDefaultIso(["en"])).toBe("AU");
    expect(resolveDefaultIso([])).toBe("AU");
    expect(resolveDefaultIso(undefined)).toBe("AU");
  });

  it("filters by name, ISO code, and dial code", () => {
    expect(filterCountries("")).toHaveLength(COUNTRIES.length);

    const united = filterCountries("united").map((entry) => entry.iso);
    expect(united).toContain("US");
    expect(united).toContain("GB");
    expect(united).toContain("AE");

    expect(filterCountries("gb").map((entry) => entry.iso)).toEqual(["GB"]);

    const plusFortyFour = filterCountries("+44").map((entry) => entry.iso);
    expect(plusFortyFour).toContain("GB");
    expect(plusFortyFour).not.toContain("AU");
    expect(filterCountries("44").map((entry) => entry.iso)).toEqual(plusFortyFour);

    expect(filterCountries("zzzz")).toEqual([]);
  });
});
