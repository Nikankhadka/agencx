/**
 * The details the privacy page and terms name that only the operator can supply.
 *
 * Every value is a bracketed placeholder on purpose: the drafted text reads
 * correctly with them filled in, and a bracket left in production is visible
 * to anyone who opens the page. Fill them here, once, and both pages follow.
 * The drafted text is not legal advice - a lawyer reviews it before real
 * clients sign up (T-032).
 */
export const LEGAL = {
  /** The company or person that operates Agencx, as it should appear on a contract. */
  entity: "[LEGAL ENTITY NAME]",
  /** Australian Business Number, or the local equivalent. */
  abn: "[ABN]",
  /** The law that governs the terms, e.g. "New South Wales, Australia". */
  jurisdiction: "[GOVERNING JURISDICTION]",
  /** Where privacy and data requests go. */
  contactEmail: "[PRIVACY CONTACT EMAIL]",
  /** The most Agencx is liable for, e.g. "AUD 100". */
  liabilityCap: "[LIABILITY CAP]",
  /** When these pages last changed in substance. */
  updated: "[DATE LAST UPDATED]",
} as const;

/**
 * How long a data request takes to answer. The operator process behind it is
 * docs/agencx/deploy.md Step 8; change the two together.
 */
export const REQUEST_DAYS = 30;
