/**
 * 32: the four selling modes on the client.
 *
 * The backend owns the inference, the stored config, and the summary; nothing
 * here recomputes those. What lives in this module is what the card has to
 * decide locally: which sentence to show for a confidence level, which label to
 * render for a key the stored map may not carry, and what a multi-select sends
 * back.
 *
 * The label defaults mirror `app/features/onboarding/selling_modes.py`. That
 * map is the same contract on both sides - the backend renders the summary with
 * it, this renders the screen - so both are pinned by a test rather than trusted
 * to stay in step.
 */

export type Mode = "orders" | "bookings" | "quotes" | "products";
export type Confidence = "high" | "medium" | "low";
export type ScheduleMode = "none" | "asap" | "slot" | "window";
export type StockMode = "none" | "flag" | "counted";
export type FulfillmentMode = "in_house" | "pickup" | "delivery" | "onsite" | "shipping";
export type AcceptanceMode = "auto" | "owner" | "deposit";
export type PaymentMode = "now" | "later" | "deposit";

export interface Capabilities {
  sell: Mode[];
  schedule: ScheduleMode;
  stock: StockMode;
  fulfillment: FulfillmentMode[];
  acceptance: AcceptanceMode;
  payment: PaymentMode;
}

/** One follow-up row on the change path. */
export type AxisKey =
  | "fulfillment"
  | "schedule"
  | "stock"
  | "acceptance"
  | "payment"
  | "lead_time";

export type LabelKey =
  | "item"
  | "items"
  | "work"
  | "add_item"
  | "time"
  | "sold_out"
  | "action";

export type SellingModeLabels = Record<LabelKey, string>;

/** The stage card's payload (``SellingModePayload`` in the backend). */
export interface SellingModeSuggestion {
  mode: Mode;
  capabilities: Capabilities;
  labels: SellingModeLabels;
  /** The ordering defaults this tenant runs on, so a row starts from the row. */
  defaults?: Record<string, number | string>;
  confidence: Confidence;
  candidates: Mode[];
  evidence: string[];
  /** Server-rendered from the stored config. Never composed here. */
  summary: string;
}

export interface SellingModePayload {
  mode: Mode;
  capabilities: Capabilities;
  labels: SellingModeLabels;
  defaults?: Record<string, number>;
}

export const MODE_TITLES: Record<Mode, string> = {
  orders: "Orders",
  bookings: "Bookings",
  quotes: "Quotes",
  products: "Products",
};

export const MODE_ORDER: Mode[] = ["orders", "bookings", "quotes", "products"];

/** The backend's neutral fallback, key for key. */
export const LABEL_DEFAULTS: SellingModeLabels = {
  item: "Item",
  items: "Items",
  work: "Work",
  add_item: "Add item",
  time: "Time",
  sold_out: "Unavailable",
  action: "Action",
};

const LABEL_KEYS = Object.keys(LABEL_DEFAULTS) as LabelKey[];

/**
 * The four default bundles from the ticket's table. Copy for the modes lives
 * here, never in a branch: nothing in this module asks what the business does.
 */
export const MODE_PRESETS: Record<Mode, { capabilities: Capabilities; labels: SellingModeLabels }> = {
  orders: {
    capabilities: {
      sell: ["orders"],
      schedule: "asap",
      stock: "flag",
      fulfillment: ["in_house", "pickup"],
      acceptance: "auto",
      payment: "now",
    },
    labels: {
      item: "Dish",
      items: "Menu",
      work: "Orders",
      add_item: "Add a dish",
      time: "Prep time",
      sold_out: "Sold out today",
      action: "Order",
    },
  },
  bookings: {
    capabilities: {
      sell: ["bookings"],
      schedule: "slot",
      stock: "none",
      fulfillment: ["onsite"],
      acceptance: "auto",
      payment: "later",
    },
    labels: {
      item: "Service",
      items: "Services",
      work: "Bookings",
      add_item: "Add a service",
      time: "Duration",
      sold_out: "Unavailable",
      action: "Book",
    },
  },
  quotes: {
    capabilities: {
      sell: ["quotes"],
      schedule: "window",
      stock: "none",
      fulfillment: ["onsite"],
      acceptance: "owner",
      payment: "later",
    },
    labels: {
      item: "Job",
      items: "Jobs",
      work: "Requests",
      add_item: "Add a job",
      time: "Visit window",
      sold_out: "Unavailable",
      action: "Request a quote",
    },
  },
  products: {
    capabilities: {
      sell: ["products"],
      schedule: "none",
      stock: "counted",
      fulfillment: ["shipping", "pickup"],
      acceptance: "auto",
      payment: "now",
    },
    labels: {
      item: "Product",
      items: "Products",
      work: "Products",
      add_item: "Add a product",
      time: "Delivery time",
      sold_out: "Out of stock",
      action: "Add to cart",
    },
  },
};

/** The axis order the merge and the follow-up rows both use. */
const SCHEDULE_ORDER: ScheduleMode[] = ["slot", "window", "asap", "none"];
const STOCK_ORDER: StockMode[] = ["counted", "flag", "none"];
const ACCEPTANCE_ORDER: AcceptanceMode[] = ["deposit", "owner", "auto"];
const PAYMENT_ORDER: PaymentMode[] = ["now", "deposit", "later"];
const FULFILLMENT_ORDER: FulfillmentMode[] = [
  "in_house",
  "pickup",
  "delivery",
  "onsite",
  "shipping",
];

/**
 * One label, with the neutral default behind it.
 *
 * A stored map that is missing a key is normal - Settings only writes what the
 * owner renamed - so the lookup never renders an empty string.
 */
export function labelFor(
  labels: Partial<Record<string, string>> | undefined,
  key: LabelKey,
): string {
  const value = labels?.[key]?.trim();
  return value ? value : LABEL_DEFAULTS[key];
}

/**
 * The label map for a set of modes: the first mode owns the wording, the
 * defaults fill anything left, and a key outside the vocabulary is dropped.
 */
export function labelsFor(
  modes: Mode[],
  overrides: Partial<Record<string, string>> = {},
): SellingModeLabels {
  const labels = { ...LABEL_DEFAULTS } as SellingModeLabels;
  const chosen = new Set<LabelKey>();
  for (const mode of modes) {
    for (const key of LABEL_KEYS) {
      if (chosen.has(key)) continue;
      labels[key] = MODE_PRESETS[mode].labels[key];
      chosen.add(key);
    }
  }
  for (const key of LABEL_KEYS) {
    const override = overrides[key]?.trim();
    if (override) labels[key] = override;
  }
  return labels;
}

function mostSpecific<T extends string>(values: T[], order: T[]): T {
  return order.find((candidate) => values.includes(candidate)) ?? order[order.length - 1]!;
}

/**
 * The bundle two or more modes add up to.
 *
 * The merge is a rule, not a guess: a time promise beats no time promise, a
 * counted stock beats a sold-out flag, and the strictest acceptance wins. Every
 * axis stays editable afterwards, so this only decides what the follow-up rows
 * start on.
 */
export function mergedCapabilities(modes: Mode[]): Capabilities {
  const picked = modes.length > 0 ? modes : [MODE_ORDER[0]!];
  const presets = picked.map((mode) => MODE_PRESETS[mode].capabilities);
  const fulfillment = FULFILLMENT_ORDER.filter((value) =>
    presets.some((preset) => preset.fulfillment.includes(value)),
  );
  return {
    sell: [...picked],
    schedule: mostSpecific(presets.map((preset) => preset.schedule), SCHEDULE_ORDER),
    stock: mostSpecific(presets.map((preset) => preset.stock), STOCK_ORDER),
    fulfillment: fulfillment.length > 0 ? fulfillment : ["in_house"],
    acceptance: mostSpecific(presets.map((preset) => preset.acceptance), ACCEPTANCE_ORDER),
    payment: mostSpecific(presets.map((preset) => preset.payment), PAYMENT_ORDER),
  };
}

/**
 * Which follow-up rows a set of picked modes actually has.
 *
 * This is the ticket's own per-mode follow-up list as data: a barber is asked
 * about time and approval, a shop about stock and shipping, a restaurant about
 * how long an order takes. Nothing branches on a business type - the picked
 * modes are the input.
 */
const ROWS_BY_MODE: Record<Mode, AxisKey[]> = {
  orders: ["fulfillment", "lead_time", "schedule", "stock", "payment"],
  bookings: ["schedule", "acceptance", "payment"],
  quotes: ["schedule", "acceptance", "payment"],
  products: ["stock", "fulfillment", "schedule", "payment"],
};

const AXIS_ORDER: AxisKey[] = [
  "fulfillment",
  "lead_time",
  "schedule",
  "stock",
  "acceptance",
  "payment",
];

export function rowsFor(modes: Mode[]): AxisKey[] {
  const picked = modes.length > 0 ? modes : [MODE_ORDER[0]!];
  return AXIS_ORDER.filter((axis) => picked.some((mode) => ROWS_BY_MODE[mode].includes(axis)));
}

/**
 * What the confirm button sends: the chosen modes, the merged bundle, the
 * labels the owner will see, and any default the owner set.
 *
 * ``mode`` is the first mode picked - the primary one - which is what the
 * interview stores and the Work screen opens on.
 */
export function buildSellingModePayload(
  modes: Mode[],
  overrides: Partial<Capabilities> = {},
  defaults: Record<string, number> = {},
): SellingModePayload {
  const picked = modes.length > 0 ? modes : [MODE_ORDER[0]!];
  return {
    mode: picked[0]!,
    capabilities: { ...mergedCapabilities(picked), ...overrides, sell: [...picked] },
    labels: labelsFor(picked),
    ...(Object.keys(defaults).length > 0 ? { defaults } : {}),
  };
}

export interface ConfirmationCopy {
  /** The server's question, in the owner's words for this confidence. */
  headline: string;
  /** The one-tap yes, or null when the guess is too weak to offer one. */
  confirm: string | null;
  change: string;
  /** The modes offered as chips instead of the yes. */
  choices: Mode[];
}

const MODE_ACTION: Record<Mode, string> = {
  orders: "order from you",
  bookings: "book with you",
  quotes: "ask you for a quote",
  products: "buy your products",
};

/**
 * The card's sentence, chosen by confidence - never by business type.
 *
 * High is a one-tap confirm, medium asks which of two, low asks the owner to
 * pick from all four. The copy names what customers *do*, because that is the
 * question the interview is asking.
 */
export function confirmationCopy(suggestion: SellingModeSuggestion): ConfirmationCopy {
  const choices = suggestion.candidates.filter((mode) => mode in MODE_ACTION);
  if (suggestion.confidence === "high") {
    return {
      headline: `It looks like customers ${MODE_ACTION[suggestion.mode]}.`,
      confirm: "Yes, that's right",
      change: "Change something",
      choices: [],
    };
  }
  if (suggestion.confidence === "medium" && choices.length === 2) {
    return {
      headline: `It looks like customers either ${MODE_ACTION[choices[0]!]} or ${
        MODE_ACTION[choices[1]!]
      }. Which is closer?`,
      confirm: null,
      change: "Neither, let me choose",
      choices,
    };
  }
  return {
    headline: "How do customers buy from you? Pick the closest.",
    confirm: null,
    change: "Choose for me",
    choices: suggestion.candidates.length > 0 ? suggestion.candidates : MODE_ORDER,
  };
}
