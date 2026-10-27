import {
  AsYouType,
  getCountries,
  getCountryCallingCode,
  getExampleNumber,
  isValidPhoneNumber,
  parsePhoneNumberFromString,
  type CountryCode,
} from "libphonenumber-js/max";
import examples from "libphonenumber-js/mobile/examples";

/**
 * Country data for the shared phone pill.
 *
 * One table covers every region libphonenumber knows, because a hand-written
 * list cannot: the old six-country table only handled the markets the
 * prototype happened to show. Regions are keyed by ISO code, never by dial
 * code - +1 alone covers 25 regions, and +7, +44, +61 and others are shared
 * too, so "find the country whose code prefixes this number" is not a country
 * lookup.
 *
 * Values are stored in international human format ("+61 412 345 678"). That
 * is what the onboarding message shows and what the Business page renders, so
 * E.164 ("+61412345678") would be readable only to machines. Both parse with
 * one call, and the trunk prefix is dropped, which the old "+61 0412..." form
 * got wrong.
 */

export const DEFAULT_ISO: CountryCode = "AU";

export interface Country {
  iso: CountryCode;
  /** Dial code, shared by several regions, e.g. "+1". */
  code: string;
  flag: string;
  name: string;
  /** Live national formatting as the owner types. */
  format: (value: string) => string;
  /** Whether the national value is a valid number for this region. */
  valid: (value: string) => boolean;
  placeholder: string;
}

const REGION_NAMES =
  typeof Intl.DisplayNames === "function"
    ? new Intl.DisplayNames(["en"], { type: "region" })
    : null;

function regionName(iso: CountryCode): string {
  try {
    return REGION_NAMES?.of(iso) ?? iso;
  } catch {
    return iso;
  }
}

function flagOf(iso: string): string {
  return String.fromCodePoint(
    ...[...iso].map((char) => 0x1f1e6 + char.charCodeAt(0) - "A".charCodeAt(0)),
  );
}

export const COUNTRIES: Country[] = getCountries()
  .map((iso) => {
    const example = getExampleNumber(iso, examples);
    return {
      iso,
      code: `+${getCountryCallingCode(iso)}`,
      flag: flagOf(iso),
      name: regionName(iso),
      format: (value: string) => new AsYouType(iso).input(value),
      valid: (value: string) => isValidPhoneNumber(value, iso),
      placeholder: example?.formatNational() ?? "Phone number",
    };
  })
  .sort((left, right) => left.name.localeCompare(right.name, "en"));

const BY_ISO = new Map(COUNTRIES.map((country) => [country.iso, country]));

// When a number is too incomplete for libphonenumber to name its region, show
// one deliberate region per shared calling code rather than an arbitrary one
// from the alphabetical list.
const PREFERRED_ISO_BY_CODE: Record<string, string> = {
  "1": "US",
  "7": "RU",
  "44": "GB",
  "47": "NO",
  "61": "AU",
  "64": "NZ",
  "212": "MA",
  "262": "RE",
  "290": "SH",
  "358": "FI",
  "590": "GP",
  "599": "CW",
  "672": "NF",
};

export function countryByIso(iso: string): Country | undefined {
  return BY_ISO.get(iso as CountryCode);
}

function countryForCallingCode(code: string): Country | undefined {
  const preferred = PREFERRED_ISO_BY_CODE[code];
  if (preferred) return countryByIso(preferred);
  return COUNTRIES.find((country) => country.code === `+${code}`);
}

export interface StoredPhone {
  country: Country;
  /** National form, including the trunk prefix where the region uses one. */
  local: string;
}

/**
 * Splits a stored value back into its country and editable national number.
 *
 * Returns null for anything that is not a phone number, so the widget can open
 * empty for an email or an address. A bare "+44" (a country picked but no
 * digits yet) resolves to its preferred region. National-only values are
 * accepted with the caller's fallback region, which is what lets a number typed
 * into the free-text contact field survive the switch to the phone pill.
 */
export function parseStoredPhone(
  value: string,
  fallbackIso: string = DEFAULT_ISO,
): StoredPhone | null {
  const trimmed = value.trim();
  if (!trimmed) return null;

  const bareCode = /^\+(\d{1,3})$/.exec(trimmed);
  if (bareCode) {
    const country = countryForCallingCode(bareCode[1]);
    return country ? { country, local: "" } : null;
  }

  const parsed =
    parsePhoneNumberFromString(trimmed) ??
    // Only digits and phone punctuation are a national number; without this
    // guard "12 Main Street" parses as a phone number with the fallback region.
    (/^[+\d\s().-]+$/.test(trimmed)
      ? parsePhoneNumberFromString(trimmed, fallbackIso as CountryCode)
      : undefined);
  if (!parsed) return null;

  const country =
    (parsed.country ? countryByIso(parsed.country) : undefined) ??
    countryForCallingCode(parsed.countryCallingCode);
  if (!country) return null;

  return { country, local: parsed.formatNational() };
}

/**
 * The value the rest of the product stores: international, grouped, trunk
 * prefix dropped ("+61 412 345 678"). An unparseable partial value keeps the
 * selected dial code rather than losing what the owner has typed.
 */
export function toInternational(local: string, iso: string): string {
  const country = countryByIso(iso) ?? countryByIso(DEFAULT_ISO);
  const value = local.trim();
  if (!country) return value;
  if (!value) return country.code;
  const parsed = parsePhoneNumberFromString(value, country.iso);
  return parsed ? parsed.formatInternational() : `${country.code} ${value}`.trim();
}

/**
 * Canonical stored form for a value that is a phone number; anything else
 * (email, address, empty) is returned untouched. Used on save so the old
 * "+61 0412..." draft migrates to "+61 412..." without an edit first.
 */
export function normalizeStoredPhone(value: string): string {
  const parsed = parseStoredPhone(value);
  return parsed ? toInternational(parsed.local, parsed.country.iso) : value;
}

/**
 * The owner's region from the browser's language list. Falls back to the
 * anchor market when the browser only names a language ("en").
 */
export function resolveDefaultIso(locales: readonly string[] | undefined): CountryCode {
  for (const locale of locales ?? []) {
    const region = regionOf(locale);
    if (region) return region as CountryCode;
  }
  return DEFAULT_ISO;
}

function regionOf(locale: string): string | undefined {
  try {
    const region = new Intl.Locale(locale).region;
    return region && countryByIso(region) ? region : undefined;
  } catch {
    // A malformed tag still gets the cheap suffix walk below.
    const parts = locale.split(/[-_]/);
    for (let index = 1; index < parts.length; index += 1) {
      const candidate = parts[index].toUpperCase();
      if (candidate.length === 2 && countryByIso(candidate)) return candidate;
    }
    return undefined;
  }
}

/** Name, ISO code, or dial code ("+44" or "44"). */
export function filterCountries(query: string): Country[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return COUNTRIES;
  const dialCode = /^\+?\d+$/.test(needle)
    ? `+${needle.replace(/^\+/, "")}`
    : null;
  return COUNTRIES.filter(
    (country) =>
      country.name.toLowerCase().includes(needle) ||
      country.iso.toLowerCase() === needle ||
      (dialCode !== null && country.code === dialCode),
  );
}
