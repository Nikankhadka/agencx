"use client";

import { createContext, useContext, useEffect, useId, useRef, useState, type ChangeEvent } from "react";
import { apiFetch } from "@/lib/api";
import { ACCEPTED_UPLOAD_EXTENSIONS } from "@/lib/onboarding";
import { Button } from "@/components/ui/Button";
import { Sheet } from "@/components/ui/Sheet";
import type { ConfirmOptions } from "@/components/ui/ConfirmDialog";
import {
  mergeIncomingCandidates,
  offeringLabel,
  reconcileAfterSave,
  reconcileOfferings,
} from "./offerings";
import type { KnowledgeRecord, KnowledgeSection, PendingOffering, ReviewOffering, ReviewWorkspace, SourceDetail } from "./types";
import { sourceLabel } from "./types";
import { CategoryPicker, type CategoryOption } from "@/components/business/CategoryPicker";
import { DESKTOP_QUERY, useMediaQuery } from "@/lib/useMediaQuery";

const PAGE_SIZE = 5;
const COLLAPSED_MOBILE = 3;
const SECTION_ORDER = ["business_overview", "hours", "location", "other"] as const;

const PROFILE_ROWS = [
  { key: "business_name", label: "Business name" },
  { key: "business_type", label: "Business type" },
  { key: "hours", label: "Hours" },
  { key: "contact", label: "Contact" },
  { key: "abn", label: "ABN" },
] as const;

type ProfileKey = (typeof PROFILE_ROWS)[number]["key"];

/** 29: the business-details fields the review can edit. Required beats the
 *  source did not find are absent, never empty rows. */
export type ReviewProfile = Partial<Record<ProfileKey, string>>;

/** Shared press feedback for the sheet's text actions: underline on hover, dim on press. */
const TEXT_PRESS = "transition-colors duration-(--duration-fast) hover:underline active:opacity-60";

/** 31: the review's one field recipe - 16/24 text on the 44px floor, matching
 *  the console's own controls rather than the 18/25 sheet-field role. */
export const FIELD = "rounded-field border border-border bg-surface px-4 py-3 text-body text-text min-h-11 outline-none placeholder:text-ink-a40 focus:border-text";

type CardRefs = { current: Map<string, HTMLInputElement> };

/** 31: ask for a reveal after the render that produced the node - expanding
 *  from read-only to editable replaces the content, so the request is applied
 *  from an effect rather than from the click handler. */
type RevealRequest = { id: string } | { add: true };

/** 31: the one focus helper. After the revealed node is laid out, focus it
 *  (unless the reveal is a scroll-only one) and bring it into view by the
 *  nearest edge, so paging and expanding never leave the keyboard behind. */
function revealNode(node: HTMLElement | null, focus = true) {
  if (!node) return;
  requestAnimationFrame(() => {
    if (focus) node.focus();
    node.scrollIntoView({ block: "nearest" });
  });
}

export function reveal(cardRefs: CardRefs, id: string | null | undefined) {
  if (!id) return;
  revealNode(cardRefs.current.get(id) ?? null);
}

/** 31: the one removal question, used from both owners of an offering card
 *  (the review and the suggestions sheet). Fixed copy, and "top" because the
 *  caller sits inside the sheet's transformed panel. */
export function removeOfferingConfirm(name: string): ConfirmOptions {
  return {
    title: `Remove ${name.trim() || "this offering"}?`,
    description: "It will not be saved to your catalog.",
    confirmLabel: "Remove",
    tone: "danger",
    layer: "top",
  };
}

/** 31: the footer discard question, pluralised from the reviewed source count.
 *  Same layer rule as the offering removal. */
export function discardConfirm(count: number): ConfirmOptions {
  const many = count > 1;
  return {
    title: many ? "Discard these sources?" : "Discard this source?",
    description: many
      ? "They are deleted, and their details and offerings are not saved."
      : "It is deleted, and its details and offerings are not saved.",
    confirmLabel: many ? "Discard sources" : "Discard source",
    tone: "danger",
    layer: "top",
  };
}

/** 31: the link replacement question. Same fixed copy and layer rule as the
 *  offering removal - the sheet sits inside the panel's transformed box. */
export function replaceLinkConfirm(): ConfirmOptions {
  return {
    title: "Replace this link?",
    description:
      "The new site will be read, and its details and offerings will replace this source.",
    confirmLabel: "Replace link",
    tone: "danger",
    layer: "top",
  };
}

/** 31: which offerings survive a link save. A different URL is a replacement,
 *  so the review reconciles against the document it replaced. The same URL is
 *  a re-read of that same row - its candidates are its own, so they merge in
 *  place and keep the id that names their source. */
export function reconcileLinkOfferings(
  previous: ReviewOffering[],
  record: KnowledgeRecord,
  replacedDocumentId: string,
  editedCandidateIds: Set<string>,
): ReviewOffering[] {
  if (record.id === replacedDocumentId) return mergeIncomingCandidates(previous, [record]);
  return reconcileOfferings(previous, record.offering_candidates ?? [], replacedDocumentId, editedCandidateIds);
}

/** 31: one link save at a time. The slot is claimed before the confirm opens,
 *  because `useConfirm` keeps a single pending entry: a second save asked while
 *  that dialog is up would replace the first promise and leave it unresolved.
 *  The handler releases the slot in its `finally`, so a cancel frees it too. */
export function claimLinkSave(slot: { current: boolean }): boolean {
  if (slot.current) return false;
  slot.current = true;
  return true;
}

/** 31: the category trigger names its panel only while that panel is in the
 *  DOM - an `aria-controls` pointing at nothing tells a screen reader less
 *  than no attribute at all. `aria-expanded` stays in both states. */
export function categoryTriggerAria(
  open: boolean,
  panelId: string,
): { "aria-expanded": boolean; "aria-controls"?: string } {
  return open
    ? { "aria-expanded": true, "aria-controls": panelId }
    : { "aria-expanded": false };
}

const CategoryContext = createContext<{
  categories: CategoryOption[];
  createCategory: (name: string) => Promise<CategoryOption>;
}>({ categories: [], createCategory: async () => { throw new Error("Category picker unavailable"); } });

interface WorkingOffering extends Omit<PendingOffering, "candidate_id"> {
  candidate_id: string;
  /** The current price input, in whichever shape it holds. */
  priceText: string;
  /** 29: the owner's words when the value is not a flat amount. */
  priceWording: string;
  priceOptions: number[];
  priceNote: string;
  possibleMatches: string[];
  support_state: "supported" | "orphaned";
  /** W-11c: any user edit/add/combine marks the row dirty; stripped before save. */
  dirty: boolean;
}

export function toWorkingOffering(item: ReviewOffering): WorkingOffering {
  return {
    ...item,
    candidate_id: item.candidate_id ?? legacyId(item.name),
    description: item.description ?? "",
    sources: item.sources ?? ["owner"],
    source_references: item.source_references ?? [],
    priceText: item.price_cents == null ? "" : formatPrice(item.price_cents),
    priceWording:
      item.price_cents == null ? (item.pricing_wording ?? "").trim() : "",
    priceOptions: item.price_options ?? [],
    priceNote: item.needs_review ? (item.price_note ?? "") : "",
    possibleMatches: item.possible_matches ?? [],
    support_state: item.support_state ?? "supported",
    source_wording: item.source_wording ?? "",
    proposed_category: item.proposed_category ?? "",
    category_ids: item.category_ids ?? null,
    primary_category_id: item.primary_category_id ?? null,
    description_origin: item.description_origin ?? "none",
    review_status: item.review_status ?? "pending",
    provenance: item.provenance ?? {},
    dirty: false,
  };
}

export interface ReviewSheetProps {
  workspace: ReviewWorkspace | null;
  suggestions?: ReviewOffering[];
  suggestionsOnly?: boolean;
  open: boolean;
  busy: boolean;
  priceConflict: string | null;
  onboarding?: boolean;
  /** 29: the business fields the source found, edited inline on the review. */
  profile?: ReviewProfile;
  /** 29: required beats the source did not find, from the onboarding state. */
  missingRequired?: string[];
  onClose: () => void;
  /** W-11c: resolves with the candidates to adopt after a batch save, or null
   *  when the caller keeps its current flow. The sheet adopts the resolved
   *  list and never re-syncs from the workspace after mount. */
  onSave: (documents: { document_id: string; sections: KnowledgeSection[] }[], offerings: PendingOffering[], acceptPriceChanges?: boolean, profile?: Record<string, string>) => Promise<PendingOffering[] | null>;
  onSaveSuggestions?: (offerings: PendingOffering[]) => Promise<void>;
  onDiscard: () => void;
  // W-11c: onboarding-only source actions. Their presence enables the actions
  // on each source row - the Business page never passes them.
  onAddSource?: (files: File[]) => Promise<KnowledgeRecord[]>;
  onReplaceSource?: (documentId: string, file: File) => Promise<KnowledgeRecord | null>;
  onRemoveSource?: (documentId: string) => Promise<void>;
  /** 31: the link editor's two doors, both optional. A replacement answers the
   *  new record plus the state's draft (the fields the site stated); an added
   *  link answers the records now in the review. */
  onReplaceLink?: (documentId: string, url: string) => Promise<{ record: KnowledgeRecord; draft: Record<string, unknown> } | null>;
  onAddLink?: (url: string) => Promise<KnowledgeRecord[]>;
  /**
   * The parent's `confirm` (its dialog renders at page level, above this
   * sheet) - the sheet asks through it before dropping a source, so the
   * dialog never renders inside the sheet's own transformed panel.
   */
  confirmRemove?: (options: ConfirmOptions) => Promise<boolean>;
}

export function ReviewSheet({ workspace, suggestions, suggestionsOnly = false, open, busy, priceConflict, onboarding = false, profile, missingRequired, onClose, onSave, onSaveSuggestions, onDiscard, onAddSource, onReplaceSource, onRemoveSource, onReplaceLink, onAddLink, confirmRemove }: ReviewSheetProps) {
  const [categories, setCategories] = useState<CategoryOption[]>([]);
  useEffect(() => {
    if (!open) return;
    apiFetch<CategoryOption[]>("/api/business/offering-categories")
      .then(setCategories)
      .catch(() => setCategories([]));
  }, [open]);
  async function createCategory(name: string) {
    const created = await apiFetch<CategoryOption>("/api/business/offering-categories", {
      method: "POST",
      body: JSON.stringify({ name }),
    });
    setCategories((current) => [...current.filter((item) => item.id !== created.id), created].sort((left, right) => left.name.localeCompare(right.name)));
    return created;
  }
  const title = suggestionsOnly
    ? "Suggestions to review"
    : onboarding
      ? "Review your information"
      : workspace?.documents[0]?.status === "draft"
        ? "Read this back"
        : "Edit what I know";
  return <Sheet open={open} onClose={onClose} variant="document" title={title}><CategoryContext.Provider value={{ categories, createCategory }}>
    {suggestionsOnly && suggestions && onSaveSuggestions ? (
      <SuggestionDocument
        key={suggestions.map((item) => item.candidate_id ?? item.name).join(",")}
        suggestions={suggestions}
        busy={busy}
        onSave={onSaveSuggestions}
        onDiscard={onDiscard}
        confirmRemove={confirmRemove}
      />
    ) : workspace ? <ReviewDocument key={workspace.id} workspace={workspace} busy={busy} priceConflict={priceConflict} onboarding={onboarding} profile={profile} missingRequired={missingRequired} onSave={onSave} onDiscard={onDiscard} onAddSource={onAddSource} onReplaceSource={onReplaceSource} onRemoveSource={onRemoveSource} onReplaceLink={onReplaceLink} onAddLink={onAddLink} confirmRemove={confirmRemove} /> : null}
  </CategoryContext.Provider></Sheet>;
}

function SuggestionDocument({ suggestions, busy, onSave, onDiscard, confirmRemove }: { suggestions: ReviewOffering[]; busy: boolean; onSave: (offerings: PendingOffering[]) => Promise<void>; onDiscard: () => void; confirmRemove?: ReviewSheetProps["confirmRemove"] }) {
  const desktop = useMediaQuery(DESKTOP_QUERY);
  const pageSize = desktop ? PAGE_SIZE : COLLAPSED_MOBILE;
  const [offerings, setOfferings] = useState(() => suggestions.map(toWorkingOffering));
  const [page, setPage] = useState(0);
  const [revealRequest, setRevealRequest] = useState<{ id: string } | null>(null);
  const cardRefs = useRef(new Map<string, HTMLInputElement>());
  const pages = offeringPageCount(offerings.length, pageSize);
  const currentPage = Math.min(page, pages - 1);
  const visible = offeringPage(offerings, currentPage, pageSize);
  useEffect(() => {
    if (!revealRequest) return;
    reveal(cardRefs, revealRequest.id);
  }, [revealRequest]);

  function gotoPage(nextPage: number) {
    const clamped = Math.min(Math.max(nextPage, 0), pages - 1);
    setPage(clamped);
    const first = offeringPage(offerings, clamped, pageSize)[0];
    if (first) setRevealRequest({ id: first.candidate_id });
  }

  function updateOffering(id: string, update: Partial<WorkingOffering>) {
    setOfferings((previous) => previous.map((item) => item.candidate_id === id ? { ...item, ...update, dirty: true } : item));
  }

  async function removeOffering(id: string) {
    const target = offerings.find((item) => item.candidate_id === id);
    if (!target) return;
    if (confirmRemove && !(await confirmRemove(removeOfferingConfirm(target.name)))) return;
    const next = offerings.filter((item) => item.candidate_id !== id);
    setOfferings(next);
    // 31: a page that no longer exists falls back to the first one.
    if (page > offeringPageCount(next.length, pageSize) - 1) setPage(0);
  }

  async function save() {
    await onSave(offerings.filter((item) => item.name.trim()).map((item) => toPendingOffering({ ...item, review_status: "approved" })));
  }

  return <div className="flex min-h-0 flex-1 flex-col">
    <div className="min-h-0 flex-1 overflow-y-auto pb-4">
      <p className="text-meta text-ink-a40">These private drafts never reach customers until you save them.</p>
      <div className="mt-4 flex flex-col gap-2">
        {visible.map((offering, index) => <OfferingCard key={offering.candidate_id} offering={offering} documents={[]} position={currentPage * pageSize + index + 1} all={offerings} editing inputRef={(node) => { if (node) cardRefs.current.set(offering.candidate_id, node); }} onChange={updateOffering} onRemove={removeOffering} onKeepBoth={() => undefined} onCombine={() => undefined} />)}
      </div>
      {pages > 1 ? <Pagination page={currentPage} pages={pages} count={offerings.length} onPage={gotoPage} pageSize={pageSize} noun="suggestions" /> : null}
    </div>
    <footer className="mt-3 flex shrink-0 gap-2 border-t border-hairline pt-3">
      <Button className="flex-1" loading={busy} onClick={() => void save()} data-testid="suggestions-save">Save suggestions</Button>
      <button type="button" onClick={onDiscard} disabled={busy} className={`${TEXT_PRESS} px-3 text-action font-medium text-ink-a40`}>Cancel</button>
    </footer>
  </div>;
}

function ReviewDocument({ workspace, busy, priceConflict, onboarding, profile, missingRequired, onSave, onDiscard, onAddSource, onReplaceSource, onRemoveSource, onReplaceLink, onAddLink, confirmRemove }: { workspace: ReviewWorkspace; busy: boolean; priceConflict: string | null; onboarding: boolean; profile?: ReviewProfile; missingRequired?: string[]; onSave: ReviewSheetProps["onSave"]; onDiscard: () => void; onAddSource?: ReviewSheetProps["onAddSource"]; onReplaceSource?: ReviewSheetProps["onReplaceSource"]; onRemoveSource?: ReviewSheetProps["onRemoveSource"]; onReplaceLink?: ReviewSheetProps["onReplaceLink"]; onAddLink?: ReviewSheetProps["onAddLink"]; confirmRemove?: ReviewSheetProps["confirmRemove"] }) {
  // Ticket 28: the collapsed cap is the mobile cap during SSR (useMediaQuery
  // defaults false server-side) and the page size at lg+; the client corrects
  // it after hydration.
  const desktop = useMediaQuery(DESKTOP_QUERY);
  const collapsedLimit = desktop ? PAGE_SIZE : COLLAPSED_MOBILE;
  // W-11c: the sheet reviews every workspace document together. The state map
  // below is seeded once per workspace.id and never re-synced from the
  // workspace after mount - W-11b retention (a close/reopen or a
  // rebuilds-after-save keeps the owner's in-session edits).
  const [sectionsByDocument, setSectionsByDocument] = useState<Map<string, KnowledgeSection[]>>(() => new Map(workspace.documents.map((doc) => [doc.id, orderedSections(doc.sections)])));
  const [offerings, setOfferings] = useState(() => (workspace.offering_candidates ?? []).map(toWorkingOffering));
  // 29: the review opens in price-editing mode when any service is unpriced.
  // Missing prices warn; they never block saving.
  const [expanded, setExpanded] = useState(() =>
    (workspace.offering_candidates ?? []).some(hasMissingPrice),
  );
  const [page, setPage] = useState(0);
  const [profileValues, setProfileValues] = useState<Record<string, string>>(
    () => ({ ...(profile ?? {}) }),
  );
  const [editingProfileField, setEditingProfileField] = useState<string | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [editingSection, setEditingSection] = useState<{ docId: string; index: number } | null>(null);
  const [sources, setSources] = useState<Map<string, SourceDetail>>(new Map());
  const [sourceLoading, setSourceLoading] = useState<string | null>(null);
  const [combine, setCombine] = useState<{ left: string; right: string; price: number | null } | null>(null);
  const [replaceTarget, setReplaceTarget] = useState<string | null>(null);
  const [replacingSource, setReplacingSource] = useState<string | null>(null);
  const [addingSources, setAddingSources] = useState(false);
  const cardRefs = useRef(new Map<string, HTMLInputElement>());
  const [revealRequest, setRevealRequest] = useState<RevealRequest | null>(null);
  // W-11c: every user edit/add/combine marks the row dirty (and enters this
  // ref) so a later replace orphans it instead of silently dropping it.
  const editedIdsRef = useRef(new Set<string>());
  const addOfferingRef = useRef<HTMLButtonElement>(null);
  const addFileRef = useRef<HTMLInputElement>(null);
  const replaceFileRef = useRef<HTMLInputElement>(null);
  // 31: the inline link editor. `documentId` null means the editor is adding a
  // source; the opener is remembered only so Cancel can return focus to it.
  const [linkEditor, setLinkEditor] = useState<{ documentId: string | null } | null>(null);
  const [linkValue, setLinkValue] = useState("");
  const [linkPending, setLinkPending] = useState(false);
  const linkSaveRef = useRef(false);
  const linkInputRef = useRef<HTMLInputElement>(null);
  const linkOpenerRef = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    if (!linkEditor) return;
    // The editor is the field the owner came for: focus it once it is laid out.
    revealNode(linkInputRef.current);
  }, [linkEditor]);
  useEffect(() => {
    if (!revealRequest) return;
    if ("id" in revealRequest) reveal(cardRefs, revealRequest.id);
    else revealNode(addOfferingRef.current);
  }, [revealRequest]);
  const pages = offeringPageCount(offerings.length);
  const currentPage = Math.min(page, pages - 1);
  const allFit = offerings.length <= collapsedLimit;
  const rowsEditable = expanded || allFit;
  const showReviewAll = !expanded && !allFit;
  const visible = expanded ? offeringPage(offerings, currentPage) : offerings.slice(0, collapsedLimit);
  const duplicateIds = duplicateOfferingIds(offerings);
  const unresolvedMatches = offerings.reduce((total, item) => total + item.possibleMatches.filter((id) => offerings.some((other) => other.candidate_id === id)).length, 0) / 2;
  const pricesMissing = offerings.some(missingPriceInWorking);
  const firstDocument = workspace.documents[0];
  const labels = workspace.documents.map(sourceLabel).join(", ");

  function sectionsFor(docId: string, doc: KnowledgeRecord): KnowledgeSection[] {
    // Docs that entered the workspace after mount (a message turn that created
    // a draft while the sheet was closed) are not in the map - fall back to
    // the record's own sections instead of showing an empty block.
    return sectionsByDocument.get(docId) ?? orderedSections(doc.sections);
  }
  function updateSections(docId: string, update: (previous: KnowledgeSection[]) => KnowledgeSection[]) {
    setSectionsByDocument((previous) => {
      const next = new Map(previous);
      next.set(docId, update(next.get(docId) ?? []));
      return next;
    });
  }
  function updateOffering(id: string, update: Partial<WorkingOffering>) {
    editedIdsRef.current.add(id);
    setOfferings((previous) => previous.map((item) => item.candidate_id === id ? { ...item, ...update, dirty: true } : item));
  }
  async function removeOffering(id: string) {
    const index = offerings.findIndex((item) => item.candidate_id === id);
    if (index < 0) return;
    if (confirmRemove && !(await confirmRemove(removeOfferingConfirm(offerings[index].name)))) return;
    // 31: focus follows what the removal revealed - the next row, else the
    // one above, else the action that adds one back.
    const survivor = offerings[index + 1] ?? offerings[index - 1];
    const next = offerings.filter((item) => item.candidate_id !== id);
    setOfferings(next);
    if (!survivor) {
      setPage(0);
      setRevealRequest({ add: true });
      return;
    }
    setPage(pageForOffering(next.indexOf(survivor)));
    setRevealRequest({ id: survivor.candidate_id });
  }
  function addOffering() {
    const candidate_id = `owner_${crypto.randomUUID()}`;
    editedIdsRef.current.add(candidate_id);
    setOfferings((previous) => {
      // W-11c: the new owner row lands right after the last owner-source row
      // (top of the list when there is none), and the sheet pages to it so
      // the focus below lands on a visible field.
      const next = insertOwnerOffering(previous, { candidate_id, name: "", description: "", price_cents: null, sources: ["owner"] as ("owner" | "document")[], source_references: [], priceText: "", priceWording: "", priceOptions: [], priceNote: "", possibleMatches: [], support_state: "supported" as const, dirty: true });
      setExpanded(true); setPage(next.page); return next.list;
    });
    setRevealRequest({ id: candidate_id });
  }
  function keepBoth(left: string, right: string) {
    setOfferings((previous) => previous.map((item) => item.candidate_id === left || item.candidate_id === right ? { ...item, possibleMatches: item.possibleMatches.filter((id) => id !== left && id !== right) } : item));
  }
  function applyCombine() {
    if (!combine) return;
    const left = offerings.find((item) => item.candidate_id === combine.left);
    const right = offerings.find((item) => item.candidate_id === combine.right);
    if (!left || !right) return;
    const retained = left.sources.includes("owner") ? left : right.sources.includes("owner") ? right : left;
    const removed = retained === left ? right : left;
    const prices = [left.price_cents, right.price_cents].filter((price): price is number => price != null);
    if (new Set(prices).size > 1 && combine.price == null) return;
    const price = combine.price ?? retained.price_cents ?? removed.price_cents;
    editedIdsRef.current.add(retained.candidate_id);
    setOfferings((previous) => previous.filter((item) => item.candidate_id !== removed.candidate_id).map((item) => item.candidate_id !== retained.candidate_id ? item : { ...retained, price_cents: price, priceText: formatPrice(price), priceWording: "", description: retained.description || removed.description, sources: [...new Set([...retained.sources, ...removed.sources])], source_references: [...(retained.source_references ?? []), ...(removed.source_references ?? [])], possibleMatches: [...new Set([...retained.possibleMatches, ...removed.possibleMatches])].filter((id) => id !== retained.candidate_id && id !== removed.candidate_id), dirty: true }));
    setCombine(null);
  }
  /** 31: the footer asks before it destroys anything, and names what goes.
   *  Onboarding owns the question. The Business > Knowledge page already asks
   *  through its own record removal for a saved source, and a draft there is
   *  not destructive, so a sheet-level question would ask twice. */
  async function handleDiscard() {
    if (onboarding && confirmRemove) {
      const confirmed = await confirmRemove(discardConfirm(workspace.documents.length));
      if (!confirmed) return;
    }
    onDiscard();
  }

  async function save() {
    if (duplicateIds.length) {
      const target = offerings.find((item) => duplicateIds.includes(item.candidate_id));
      if (target) { setExpanded(true); setPage(Math.floor(offerings.indexOf(target) / PAGE_SIZE)); setRevealRequest({ id: target.candidate_id }); }
      return;
    }
    const documents = workspace.documents.map((doc) => ({ document_id: doc.id, sections: sectionsFor(doc.id, doc) }));
    // 29: only fields the owner actually changed ride the batch, so an
    // untouched review never rewrites a profile field it merely displayed.
    const profilePatch = profilePatchFor(profileValues, profile);
    const adopted = await onSave(
      documents,
      offerings.filter((item) => item.name.trim()).map(toPendingOffering),
      priceConflict !== null,
      Object.keys(profilePatch).length ? profilePatch : undefined,
    );
    if (adopted) setOfferings(reconcileAfterSave(offerings, adopted, workspace.documents, editedIdsRef.current).map(toWorkingOffering));
  }
  async function loadSource(docId: string) { if (sources.has(docId) || sourceLoading) return; setSourceLoading(docId); try { const detail = await apiFetch<SourceDetail>(`/api/knowledge/records/${docId}/source`); setSources((previous) => { const next = new Map(previous); next.set(docId, detail); return next; }); } finally { setSourceLoading(null); } }
  /** 31: fold accepted records into the review without disturbing its edits.
   *  Shared by the file and link doors so both adopt the same way. */
  function adoptRecords(records: KnowledgeRecord[]) {
    if (records.length === 0) return;
    setSectionsByDocument((previous) => {
      const next = new Map(previous);
      for (const record of records) next.set(record.id, orderedSections(record.sections));
      return next;
    });
    setOfferings((previous) => {
      const merged = mergeIncomingCandidates(previous, records);
      return merged.map((item, index) => {
        const working = toWorkingOffering(item);
        if (index < previous.length && previous[index].dirty) {
          working.dirty = true;
          editedIdsRef.current.add(working.candidate_id);
        }
        return working;
      });
    });
  }
  async function handleAddFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (files.length === 0 || !onAddSource) return;
    setAddingSources(true);
    try {
      adoptRecords(await onAddSource(files));
    } finally {
      setAddingSources(false);
    }
  }
  /** 31: a URL row edits in place; a file row keeps the picker. */
  function openLinkEditor(documentId: string | null, opener: HTMLButtonElement) {
    linkOpenerRef.current = opener;
    setLinkValue(documentId === null ? "" : workspace.documents.find((doc) => doc.id === documentId)?.filename ?? "");
    setLinkEditor({ documentId });
  }
  function cancelLink() {
    // 31: cancel is not a source change - no request, no document edit.
    setLinkEditor(null);
    linkOpenerRef.current?.focus();
  }
  async function saveLink() {
    const editor = linkEditor;
    const trimmed = linkValue.trim();
    const documentId = editor?.documentId ?? null;
    if (!editor || !trimmed) return;
    // 31: claim the slot before the confirm opens, so an impatient second Save
    // never reaches the endpoint (see claimLinkSave). Every path below releases
    // it, cancel included.
    if (!claimLinkSave(linkSaveRef)) return;
    setLinkPending(true);
    try {
      if (documentId !== null) {
        if (!onReplaceLink) return;
        if (confirmRemove && !(await confirmRemove(replaceLinkConfirm()))) return;
        const result = await onReplaceLink(documentId, trimmed);
        if (!result) return;
        const { record, draft } = result;
        setSectionsByDocument((previous) => {
          const next = new Map(previous);
          next.delete(documentId);
          next.set(record.id, orderedSections(record.sections));
          return next;
        });
        setSources((previous) => {
          const next = new Map(previous);
          next.delete(documentId);
          return next;
        });
        setOfferings((previous) => reconcileLinkOfferings(previous, record, documentId, editedIdsRef.current).map(toWorkingOffering));
        // 31: the site fields it stated win; a field it omitted is absent from
        // the draft, so the value on screen survives.
        setProfileValues((previous) => {
          const next = { ...previous };
          for (const { key } of PROFILE_ROWS) {
            if (key in draft) next[key] = String(draft[key] ?? "");
          }
          return next;
        });
        setLinkEditor(null);
        // 31: a same-URL re-read keeps this row, so its opener is still the
        // control the owner came from and focus goes back to it. A replacement
        // swapped the row out; that node is gone, and focus is left alone.
        if (record.id === documentId) revealNode(linkOpenerRef.current);
        return;
      }
      if (!onAddLink) return;
      const records = await onAddLink(trimmed);
      if (records.length > 0) {
        adoptRecords(records);
        setLinkEditor(null);
      }
    } finally {
      linkSaveRef.current = false;
      setLinkPending(false);
    }
  }
  const linkEditorForm = (
    <div className="mt-3 flex items-center gap-2">
      <input
        ref={linkInputRef}
        data-testid="review-link-input"
        aria-label="Link address"
        placeholder="https://"
        value={linkValue}
        disabled={linkPending}
        onChange={(event) => setLinkValue(event.target.value)}
        className={`min-w-0 flex-1 ${FIELD}`}
      />
      <button type="button" aria-label="Save link" disabled={busy || linkPending || !linkValue.trim()} onClick={() => void saveLink()} className={`${TEXT_PRESS} shrink-0 text-action font-medium text-accent-active disabled:opacity-40`}>Save</button>
      <button type="button" aria-label="Cancel link" disabled={linkPending} onClick={cancelLink} className={`${TEXT_PRESS} shrink-0 text-action text-ink-a40 disabled:opacity-40`}>Cancel</button>
    </div>
  );
  async function handleReplaceFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    const documentId = replaceTarget;
    setReplaceTarget(null);
    if (!file || !documentId || !onReplaceSource) return;
    setReplacingSource(documentId);
    try {
      // null means the upload failed - the page's DELETE never fired and the
      // old document is untouched, so everything below stays as it was.
      const next = await onReplaceSource(documentId, file);
      if (!next) return;
      setSectionsByDocument((previous) => {
        const updated = new Map(previous);
        updated.delete(documentId);
        updated.set(next.id, orderedSections(next.sections));
        return updated;
      });
      setSources((previous) => { const updated = new Map(previous); updated.delete(documentId); return updated; });
      setOfferings((previous) => reconcileOfferings(previous, next.offering_candidates ?? [], documentId, editedIdsRef.current).map(toWorkingOffering));
    } finally {
      setReplacingSource(null);
    }
  }
  async function handleRemoveSource(documentId: string) {
    if (!onRemoveSource) return;
    if (confirmRemove) {
      const target = workspace.documents.find((doc) => doc.id === documentId);
      const confirmed = await confirmRemove({
        title: `Remove ${target ? sourceLabel(target) : "this source"}?`,
        description: "Anything it taught your assistant goes with it.",
        confirmLabel: "Remove",
        tone: "danger",
        layer: "top",
      });
      if (!confirmed) return;
    }
    try {
      await onRemoveSource(documentId);
      setSectionsByDocument((previous) => { const next = new Map(previous); next.delete(documentId); return next; });
      setSources((previous) => { const next = new Map(previous); next.delete(documentId); return next; });
    } catch {
      // The page surfaces the failure through reviewError; nothing to drop.
    }
  }

  const intro = onboarding
    ? workspace.documents.length > 1
      ? `Here's what I found in ${labels}. Review them before you use them.`
      : `Here's what I found in ${sourceLabel(firstDocument)}. Review it before you use it.`
    : `From ${labels}. Your assistant answers from the reviewed facts below.`;

  function gotoPage(next: number) {
    const clamped = Math.min(Math.max(next, 0), pages - 1);
    setPage(clamped);
    const first = offeringPage(offerings, clamped)[0];
    if (first) setRevealRequest({ id: first.candidate_id });
  }

  const profileRows = PROFILE_ROWS.map((row) => ({
    ...row,
    value: (profileValues[row.key] ?? "").trim(),
  })).filter((row) => row.value.length > 0);

  // 29: offerings lead in both modes - they are what the review exists to
  // check. Business details are context the owner can correct inline, and the
  // source line follows. DOM order matches visual order; no CSS `order`.
  const offeringsSection = (
    <section className="mt-4">
      <h3 className="text-row-label font-medium text-text">What you offer</h3>
      <p className="mt-1 text-meta text-ink-a40">{offerings.length} retained {offerings.length === 1 ? "offering" : "offerings"}{unresolvedMatches ? `, ${unresolvedMatches} possible ${unresolvedMatches === 1 ? "duplicate" : "duplicates"} to check` : ""}.</p>
      {pricesMissing ? <p role="status" data-testid="review-missing-prices" className="mt-3 rounded-field bg-warning-subtle p-3 text-meta text-text">{'No prices found here. Add a price, or write it your way, like "from $30".'}</p> : null}
      {offerings.length === 0 ? <p className="mt-3 rounded-field bg-surface-container p-3 text-prose text-text">No offerings yet.</p> : null}
      <div className="mt-3 flex flex-col gap-2">{visible.map((offering, index) => <OfferingCard key={offering.candidate_id} offering={offering} documents={workspace.documents} position={(expanded ? currentPage * PAGE_SIZE : 0) + index + 1} all={offerings} editing={rowsEditable} inputRef={(node) => { if (node) cardRefs.current.set(offering.candidate_id, node); }} onChange={updateOffering} onRemove={removeOffering} onKeepBoth={keepBoth} onCombine={(left, right) => setCombine({ left, right, price: null })} />)}</div>
      {expanded && offerings.length > PAGE_SIZE ? <Pagination page={currentPage} pages={pages} count={offerings.length} onPage={gotoPage} /> : null}
      <div className="mt-3 flex items-center justify-between">
        {showReviewAll ? <button type="button" onClick={() => { setExpanded(true); setPage(0); setRevealRequest({ id: offerings[0].candidate_id }); }} className={`${TEXT_PRESS} text-action font-medium text-accent-active`}>Review all {offerings.length} offerings</button> : <span />}
        <button ref={addOfferingRef} type="button" onClick={addOffering} className={`${TEXT_PRESS} text-action font-medium text-accent-active`}>Add offering</button>
      </div>
      {duplicateIds.length ? <p role="alert" className="mt-2 text-meta text-danger">Two retained offerings have the same name. Go to the highlighted offering to correct it.</p> : null}
    </section>
  );

  const businessDetailsSection = profile && (profileRows.length > 0 || missingRequired?.length) ? (
    <section className="mt-6">
      <h3 className="text-row-label font-medium text-text">Business details</h3>
      {profileRows.length > 0 ? <div className="mt-2">{profileRows.map((row) => <ProfileRow key={row.key} field={row.key} label={row.label} value={row.value} editing={editingProfileField === row.key} onEdit={() => setEditingProfileField(row.key)} onDone={() => setEditingProfileField(null)} onChange={(value) => setProfileValues((previous) => ({ ...previous, [row.key]: value }))} />)}</div> : null}
      {missingRequired?.length ? <p className="mt-4 text-meta text-ink-a40" data-testid="review-missing-required">{"I'll ask next: "}{missingRequired.join(", ")}.</p> : null}
    </section>
  ) : null;

  const sourcesSection = (
    <section className="mt-6">
      <h3 className="text-row-label font-medium text-text">Sources</h3>
      <div className="mt-2 flex flex-col gap-2">
        {workspace.documents.map((doc) => {
          const label = sourceLabel(doc);
          const failed = doc.status === "failed";
          const replacing = replacingSource === doc.id;
          const actionable = doc.status === "draft" || failed;
          const canRemove = actionable && onRemoveSource !== undefined;
          // 31: a URL row edits its address in place; a file row keeps the
          // picker. Neither action is offered by the Business surface.
          const canEditLink = actionable && doc.doc_type === "website" && onReplaceLink !== undefined;
          const canReplaceFile = actionable && doc.doc_type !== "website" && onReplaceSource !== undefined;
          const editingThis = linkEditor?.documentId === doc.id;
          return <div key={doc.id} className="rounded-card border border-hairline px-3 py-3">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-prose text-text">{label}</p>
                {failed ? <p className="mt-1 text-meta text-danger">{workspace.errors?.[doc.id] ?? "Failed"}</p> : workspace.errors?.[doc.id] ? <p className="mt-1 text-meta text-danger">{workspace.errors[doc.id]}</p> : null}
              </div>
              {canRemove || canEditLink || canReplaceFile ? <div className="flex shrink-0 items-center gap-2">
                {canEditLink ? <button type="button" disabled={busy || addingSources || replacingSource !== null || linkPending} onClick={(event) => openLinkEditor(doc.id, event.currentTarget)} aria-label={`Edit link for ${label}`} data-testid="review-edit-link" className={`${TEXT_PRESS} text-action font-medium text-accent-active disabled:opacity-40`}>Edit link</button> : null}
                {canReplaceFile ? <button type="button" disabled={busy || addingSources || replacingSource !== null || linkPending} onClick={() => { setReplaceTarget(doc.id); replaceFileRef.current?.click(); }} aria-label={`Replace ${label}`} data-testid="review-replace-source" className={`${TEXT_PRESS} text-action font-medium text-accent-active disabled:opacity-40`}>{replacing ? "Replacing\u2026" : "Replace"}</button> : null}
                {canRemove ? <button type="button" disabled={busy || addingSources || replacingSource !== null || linkPending} onClick={() => void handleRemoveSource(doc.id)} aria-label={`Remove ${label}`} data-testid="review-remove-source" className={`${TEXT_PRESS} text-action text-ink-a40 disabled:opacity-40`}>Remove</button> : null}
              </div> : null}
            </div>
            {editingThis ? linkEditorForm : null}
          </div>;
        })}
      </div>
      <div className="mt-3 flex items-center gap-4">
        {onAddLink ? <button type="button" disabled={busy || replacingSource !== null || linkPending} onClick={(event) => openLinkEditor(null, event.currentTarget)} data-testid="review-add-link" className={`${TEXT_PRESS} text-action font-medium text-accent-active disabled:opacity-40`}>Add a link</button> : null}
        {onAddSource ? <button type="button" disabled={busy || replacingSource !== null || addingSources || linkPending} onClick={() => addFileRef.current?.click()} data-testid="review-add-file" className={`${TEXT_PRESS} text-action font-medium text-accent-active disabled:opacity-40`}>{addingSources ? "Adding\u2026" : "Add a file"}</button> : null}
      </div>
      {linkEditor?.documentId === null ? linkEditorForm : null}
      <input ref={addFileRef} type="file" multiple accept={ACCEPTED_UPLOAD_EXTENSIONS.join(",")} className="hidden" data-testid="review-add-input" onChange={(event) => void handleAddFiles(event)} />
      <input ref={replaceFileRef} type="file" accept={ACCEPTED_UPLOAD_EXTENSIONS.join(",")} className="hidden" data-testid="review-replace-input" onChange={(event) => void handleReplaceFile(event)} />
    </section>
  );

  // 29: the structured sections are what the owner reads when they want the
  // detail; the sheet leads with the services. Closed by default, and the
  // content is not rendered until opened - the Source text stays out of the
  // default view.
  const documentDetailsSection = (
    <details className="mt-6 rounded-card border border-hairline p-3" open={detailsOpen} onToggle={(event) => setDetailsOpen(event.currentTarget.open)}>
      <summary data-testid="review-more-about-source" className={`cursor-pointer ${TEXT_PRESS} text-action font-medium text-accent-active`}>More about what I read</summary>
      {detailsOpen ? <div>{workspace.documents.map((doc) => { const sections = sectionsFor(doc.id, doc); const label = sourceLabel(doc); return <div key={doc.id} className="mt-4">{workspace.documents.length > 1 ? <p className="text-meta text-ink-a40">From {label}</p> : null}{doc.extraction_status === "partial" || doc.extraction_status === "failed" ? <p role="status" className="mt-3 rounded-field bg-warning-subtle p-2 text-meta text-text">{doc.extraction_status === "failed" ? "I could not read the offerings from this source." : "I could not read all of this source."} Add anything missing, or check the original source.</p> : null}<KnowledgeDocument sections={sections} editingSection={editingSection?.docId === doc.id ? editingSection.index : null} onEdit={(index) => setEditingSection((current) => index === null || (current?.docId === doc.id && current.index === index) ? null : { docId: doc.id, index })} onChange={(index, update) => updateSections(doc.id, (previous) => previous.map((section, position) => position === index ? { ...section, ...update } : section))} onRemove={(index) => updateSections(doc.id, (previous) => previous.filter((_, position) => position !== index))} onAddOther={() => { updateSections(doc.id, (previous) => [...previous, { heading: "New information", body: "", kind: "other" }]); setEditingSection({ docId: doc.id, index: sections.length }); }} /><details className="mt-4 rounded-card border border-hairline p-3" onToggle={(event) => { if (event.currentTarget.open) void loadSource(doc.id); }}><summary className={`cursor-pointer ${TEXT_PRESS} text-action font-medium text-accent-active`}>View original source</summary>{sourceLoading === doc.id ? <p className="mt-3 text-meta text-ink-a40">Loading source…</p> : null}{sources.get(doc.id) ? <><p className="mt-3 text-meta text-ink-a40">{sources.get(doc.id)!.is_fallback ? "This legacy source only retains its saved reviewed text." : "Original extracted source. It does not answer customers."}</p><pre className="mt-3 whitespace-pre-wrap break-words font-sans text-prose text-text">{sources.get(doc.id)!.text}</pre></> : null}</details></div>; })}</div> : null}
    </details>
  );

  return <div className="flex min-h-0 flex-1 flex-col">
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto pb-4">
      <p className="text-meta text-ink-a40">{intro}</p>
      {offeringsSection}{businessDetailsSection}{sourcesSection}{documentDetailsSection}
    </div>
    {combine ? <CombinePreview combine={combine} offerings={offerings} onPrice={(price) => setCombine({ ...combine, price })} onCancel={() => setCombine(null)} onConfirm={applyCombine} /> : null}
    {priceConflict ? <p role="alert" className="mt-3 rounded-card bg-warning-subtle p-3 text-meta text-text">{priceConflict}</p> : null}
    <footer className="mt-3 flex shrink-0 gap-2 border-t border-hairline pt-3"><Button className="flex-1" loading={busy} onClick={save} data-testid={onboarding ? "onboarding-knowledge-save" : "knowledge-save"}>{onboarding ? "Use this information" : priceConflict ? "Confirm price changes" : firstDocument?.status === "draft" ? "Save it" : "Save changes"}</Button><button type="button" onClick={() => void handleDiscard()} disabled={busy} className={`px-3 ${TEXT_PRESS} text-action font-medium text-ink-a40`} data-testid={onboarding ? "onboarding-knowledge-discard" : "knowledge-discard"}>{onboarding ? (workspace.documents.length > 1 ? "Discard sources" : "Discard source") : firstDocument?.status === "draft" ? "Discard draft" : "Remove source"}</button></footer>
  </div>;
}

function ProfileRow({ field, label, value, editing, onEdit, onDone, onChange }: { field: ProfileKey; label: string; value: string; editing: boolean; onEdit: () => void; onDone: () => void; onChange: (value: string) => void }) {
  return <div data-testid={`review-profile-${field}`} className="flex items-center justify-between gap-3 border-b border-hairline py-2 last:border-b-0">
    <span className="shrink-0 text-meta text-ink-a40">{label}</span>
    {editing ? <div className="flex min-w-0 flex-1 items-center gap-2">
      <input value={value} aria-label={label} autoFocus onChange={(event) => onChange(event.target.value)} className={`min-w-0 flex-1 ${FIELD}`} />
      <button type="button" onClick={onDone} className={`${TEXT_PRESS} shrink-0 text-action font-medium text-accent-active`}>Done</button>
    </div> : <div className="flex min-w-0 items-center gap-3">
      <span className="min-w-0 truncate text-body-sm text-text">{value}</span>
      <button type="button" onClick={onEdit} data-testid={`review-profile-edit-${field}`} className="shrink-0 text-chip font-medium text-accent-active transition-opacity duration-(--duration-fast) hover:underline active:opacity-60">Edit</button>
    </div>}
  </div>;
}

function OfferingCard({ offering, documents, position, all, editing, inputRef, onChange, onRemove, onKeepBoth, onCombine }: { offering: WorkingOffering; documents: KnowledgeRecord[]; position: number; all: WorkingOffering[]; editing: boolean; inputRef: (node: HTMLInputElement | null) => void; onChange: (id: string, update: Partial<WorkingOffering>) => void; onRemove: (id: string) => void; onKeepBoth: (left: string, right: string) => void; onCombine: (left: string, right: string) => void }) {
  const matches = all.filter((item) => offering.possibleMatches.includes(item.candidate_id));
  const priceValue = offering.priceText || offering.priceWording;
  return <article className={`rounded-card border p-3 ${matches.length ? "border-text bg-surface" : "border-border bg-surface"}`}><div className="flex items-start justify-between gap-2"><span className="text-meta text-ink-a40">{offeringLabel(offering, documents)}{offering.source_references?.length ? ` · ${offering.source_references.length} source ${offering.source_references.length === 1 ? "reference" : "references"}` : ""}</span>{editing ? <button type="button" onClick={() => onRemove(offering.candidate_id)} className={`${TEXT_PRESS} text-action text-ink-a40`}>Remove</button> : null}</div>
    {editing ? <><div className="mt-2 flex gap-2"><input ref={inputRef} value={offering.name} aria-label={`Offering ${position} name`} placeholder="Offering" onChange={(event) => onChange(offering.candidate_id, { name: event.target.value })} className={`min-w-0 flex-1 ${FIELD}`} /><input value={priceValue} aria-label={`Offering ${position} price`} placeholder="Price" onChange={(event) => onChange(offering.candidate_id, { ...priceInputUpdate(event.target.value), priceOptions: [] })} className={`w-24 ${FIELD}`} /></div><ReviewCategoryControl offering={offering} onChange={onChange} /><textarea value={offering.description} aria-label={`Offering ${position} description`} placeholder="Description (optional)" rows={2} onChange={(event) => onChange(offering.candidate_id, { description: event.target.value })} className={`mt-2 w-full resize-y ${FIELD}`} /></> : <><div className="mt-2 flex justify-between gap-3"><h4 className="text-row-label font-medium text-text">{offering.name}</h4><span className="shrink-0 text-row-label text-text">{priceValue || "Price not set"}</span></div>{offering.description ? <p className="mt-1 whitespace-pre-line text-prose text-text">{offering.description}</p> : null}</>}
    {offering.priceNote ? <p className="mt-2 rounded-field bg-warning-subtle p-2 text-meta text-text">Check this price: {offering.priceNote}</p> : null}
    {offering.priceOptions.length > 1 ? <div role="alert" className="mt-2 text-meta text-text">Choose a price: {offering.priceOptions.map((price) => <button key={price} type="button" onClick={() => onChange(offering.candidate_id, { price_cents: price, priceText: formatPrice(price), priceWording: "", priceOptions: [], wording_options: [] })} className={`${TEXT_PRESS} ml-2 text-action text-accent-active`}>Use {formatPrice(price)}</button>)}</div> : null}
    {matches.map((match) => <div key={match.candidate_id} className="mt-3 text-meta text-text"><p>This may be the same offering as <strong>{match.name}</strong>. Both remain separate until you decide.</p><div className="mt-2 flex gap-3"><button type="button" onClick={() => onCombine(offering.candidate_id, match.candidate_id)} className={`${TEXT_PRESS} text-action font-medium text-accent-active`}>Combine</button><button type="button" onClick={() => onKeepBoth(offering.candidate_id, match.candidate_id)} className={`${TEXT_PRESS} text-action text-ink-a40`}>Keep both</button></div></div>)}</article>;
}

function ReviewCategoryControl({ offering, onChange }: { offering: WorkingOffering; onChange: (id: string, update: Partial<WorkingOffering>) => void }) {
  const { categories, createCategory } = useContext(CategoryContext);
  // 31: one trigger and one picker per card, collapsed until asked for. The
  // state is local so a card knows nothing about the sheet's own layout.
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const pickerRef = useRef<HTMLDivElement>(null);
  const panelId = useId();
  const selectedIds = offering.category_ids ?? [];
  useEffect(() => {
    if (!open) return;
    // Scroll-only: `focusSearch` puts focus in the field the owner came for.
    revealNode(pickerRef.current, false);
  }, [open]);
  async function acceptSuggestion() {
    const suggestion = offering.proposed_category?.trim();
    if (!suggestion) return;
    const match = categories.find((category) => category.name.trim().toLocaleLowerCase() === suggestion.toLocaleLowerCase());
    const category = match ?? await createCategory(suggestion);
    const ids = [...new Set([...selectedIds, category.id])];
    onChange(offering.candidate_id, { category_ids: ids, primary_category_id: offering.primary_category_id ?? category.id });
  }
  return <div className="mt-3">
    <button ref={triggerRef} type="button" {...categoryTriggerAria(open, panelId)} data-testid="review-category-trigger" onClick={() => setOpen((current) => !current)} className={`${TEXT_PRESS} text-action font-medium text-accent-active`}>{selectedIds.length ? `Categories (${selectedIds.length})` : "Add category"}</button>
    {open ? <div id={panelId} ref={pickerRef}>
      {offering.proposed_category ? <p className="mt-2 text-meta text-ink-a40">Suggested category: {offering.proposed_category} <button type="button" onClick={() => void acceptSuggestion()} className={`${TEXT_PRESS} ml-1 font-medium text-accent-active`}>Use suggestion</button></p> : null}
      <CategoryPicker
        focusSearch
        categories={categories}
        selectedIds={selectedIds}
        primaryId={offering.primary_category_id ?? null}
        onChange={(category_ids, primary_category_id) => onChange(offering.candidate_id, { category_ids, primary_category_id })}
        onCreate={createCategory}
      />
      <button type="button" data-testid="review-category-done" onClick={() => { setOpen(false); triggerRef.current?.focus(); }} className={`${TEXT_PRESS} mt-2 text-action font-medium text-accent-active`}>Done</button>
    </div> : null}
  </div>;
}

export function KnowledgeDocument({ sections, editingSection = null, onEdit, onChange, onRemove, onAddOther }: { sections: KnowledgeSection[]; editingSection?: number | null; onEdit?: (index: number | null) => void; onChange?: (index: number, update: Partial<KnowledgeSection>) => void; onRemove?: (index: number) => void; onAddOther?: () => void }) {
  return <div className="mt-3 flex flex-col gap-4">{sections.map((section, index) => <section key={`${section.kind}-${section.heading}-${index}`} className="rounded-card border border-hairline p-3"><div className="flex items-center justify-between gap-3">{editingSection === index ? <input value={section.heading} aria-label="Section heading" onChange={(event) => onChange?.(index, { heading: event.target.value })} className="min-w-0 rounded-field border border-border bg-surface px-4 py-3 text-row-label font-medium text-text min-h-11" /> : <h4 className="text-label font-medium uppercase text-ink-a40">{section.heading}</h4>}{onEdit ? <div className="flex gap-3"><button type="button" onClick={() => onEdit(editingSection === index ? null : index)} className={`${TEXT_PRESS} text-action text-accent-active`}>{editingSection === index ? "Done" : "Edit"}</button>{section.kind === "other" ? <button type="button" onClick={() => onRemove?.(index)} className={`${TEXT_PRESS} text-action text-ink-a40`}>Remove</button> : null}</div> : null}</div>{editingSection === index ? <textarea value={section.body} rows={4} aria-label={`${section.heading} details`} onChange={(event) => onChange?.(index, { body: event.target.value })} className={`mt-2 w-full resize-y ${FIELD}`} /> : <FormattedBody body={section.body} />}</section>)}{onAddOther ? <button type="button" onClick={onAddOther} className={`text-left ${TEXT_PRESS} text-action font-medium text-accent-active`}>Add other information</button> : null}</div>;
}

function FormattedBody({ body }: { body: string }) { return <div className="mt-2 whitespace-pre-line break-words text-prose text-text">{body.split("\n").map((line, index) => line.startsWith("- ") || line.startsWith("• ") ? <div key={index} className="pl-4 before:mr-2 before:content-['•']">{line.slice(2)}</div> : <p key={index} className={line ? "" : "h-3"}>{line}</p>)}</div>; }
function CombinePreview({ combine, offerings, onPrice, onCancel, onConfirm }: { combine: { left: string; right: string; price: number | null }; offerings: WorkingOffering[]; onPrice: (price: number) => void; onCancel: () => void; onConfirm: () => void }) { const pair = offerings.filter((item) => item.candidate_id === combine.left || item.candidate_id === combine.right); const retained = pair.find((item) => item.sources.includes("owner")) ?? pair[0]; const prices = [...new Set(pair.map((item) => item.price_cents).filter((price): price is number => price != null))]; if (!retained) return null; return <section className="mt-3 rounded-card border border-text bg-surface p-3"><h3 className="text-row-label font-medium text-text">Combine offerings</h3><p className="mt-1 text-meta text-text">This keeps {retained.name}, {retained.description || "the available description"}, and {prices.length > 1 ? "the price you choose" : retained.priceText || retained.priceWording || "no price"}. Source evidence is combined.</p>{prices.length > 1 ? <div className="mt-2"><p className="text-meta text-text">Choose the retained price.</p>{prices.map((price) => <button key={price} type="button" onClick={() => onPrice(price)} className={`mr-2 mt-2 rounded-full border px-3 py-1 text-action transition-colors duration-(--duration-fast) hover:bg-surface-container ${combine.price === price ? "border-text bg-surface text-text" : "border-border text-text"}`}>{formatPrice(price)}</button>)}</div> : null}<div className="mt-3 flex gap-3"><button type="button" onClick={onConfirm} disabled={prices.length > 1 && combine.price == null} className={`${TEXT_PRESS} text-action font-medium text-accent-active disabled:opacity-50`}>Confirm combine</button><button type="button" onClick={onCancel} className={`${TEXT_PRESS} text-action text-ink-a40`}>Cancel</button></div></section>; }
export function Pagination({ page, pages, count, onPage, pageSize = PAGE_SIZE, noun = "offerings" }: { page: number; pages: number; count: number; onPage: (page: number) => void; pageSize?: number; noun?: string }) { return <div className="mt-4 flex flex-col gap-2 text-meta text-text"><div className="flex items-center justify-between"><button type="button" disabled={page === 0} onClick={() => onPage(page - 1)} className={`${TEXT_PRESS} text-action text-accent-active disabled:opacity-40`}>Previous</button><span>Page {page + 1} of {pages}</span><button type="button" disabled={page === pages - 1} onClick={() => onPage(page + 1)} className={`${TEXT_PRESS} text-action text-accent-active disabled:opacity-40`}>Next</button></div><p className="text-center">Showing {page * pageSize + 1}-{Math.min((page + 1) * pageSize, count)} of {count} {noun}</p></div>; }
export function offeringPageCount(count: number, pageSize = PAGE_SIZE) { return Math.max(1, Math.ceil(count / pageSize)); }
export function offeringPage<T>(offerings: T[], page: number, pageSize = PAGE_SIZE) { return offerings.slice(page * pageSize, page * pageSize + pageSize); }
export function pageForOffering(index: number) { return Math.max(0, Math.floor(index / PAGE_SIZE)); }
/** W-11c: where a fresh owner row lands - right after the last owner-source
 *  row, or at the top of the list when there is none - and the page that
 *  shows it. Pure so the insertion rule is unit-testable. */
export function insertOwnerOffering(offerings: WorkingOffering[], item: WorkingOffering): { list: WorkingOffering[]; page: number } {
  const ownerEnd = offerings.map((offering) => offering.sources.includes("owner")).lastIndexOf(true);
  const insertAt = ownerEnd + 1;
  return { list: [...offerings.slice(0, insertAt), item, ...offerings.slice(insertAt)], page: pageForOffering(insertAt) };
}
function orderedSections(sections: KnowledgeSection[]) { return [...sections].filter((section) => section.body.trim()).sort((left, right) => SECTION_ORDER.indexOf(left.kind ?? "other") - SECTION_ORDER.indexOf(right.kind ?? "other")); }
function duplicateOfferingIds(offerings: WorkingOffering[]) { const seen = new Map<string, string>(); const duplicates: string[] = []; for (const item of offerings) { const key = item.name.normalize("NFKC").trim().toLowerCase(); if (key && seen.has(key)) duplicates.push(item.candidate_id); else if (key) seen.set(key, item.candidate_id); } return duplicates; }
function legacyId(name: string) { return `legacy_${name.normalize("NFKC").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-")}`; }
function hasMissingPrice(item: PendingOffering) { return item.price_cents == null && !(item.pricing_wording ?? "").trim(); }
function missingPriceInWorking(item: WorkingOffering) { return !item.priceText.trim() && !item.priceWording.trim(); }
/** 29: the one price input in two shapes. A parseable amount stays a number;
 *  anything else is the owner's own wording, kept verbatim. */
/** 29: the batch's profile patch. Only the editable rows are considered, and
 *  only when the owner changed one - the state response also carries lists
 *  (services), which must never reach a string patch. */
export function profilePatchFor(
  values: Record<string, unknown>,
  original?: ReviewProfile,
): Record<string, string> {
  return Object.fromEntries(
    PROFILE_ROWS.map(({ key }) => [
      key,
      String(values[key] ?? "").trim(),
    ] as const).filter(
      ([key, value]) =>
        value.length > 0 && value !== String(original?.[key] ?? "").trim(),
    ),
  );
}
export function priceInputUpdate(
  value: string,
): Pick<WorkingOffering, "priceText" | "priceWording" | "wording_options"> {
  // An explicit edit is the owner's decision, so it clears the server's
  // conflicting wordings just as the input clears priceOptions below.
  return parsePriceCents(value) == null
    ? { priceText: "", priceWording: value, wording_options: [] }
    : { priceText: value, priceWording: "", wording_options: [] };
}
export function toPendingOffering(item: WorkingOffering): PendingOffering {
  // Strips the WorkingOffering-only fields (priceText, priceWording,
  // priceOptions, priceNote, possibleMatches, dirty) before the row goes over
  // the wire. A number becomes price_cents and clears the wording; any other
  // non-empty value becomes pricing_wording with price_cents null.
  const cents = parsePriceCents(item.priceText);
  const wording = (item.priceWording || item.priceText).trim();
  return {
    candidate_id: item.candidate_id,
    name: item.name.trim(),
    description: item.description,
    price_cents: cents,
    pricing_wording: cents == null ? wording : "",
    sources: item.sources,
    source_references: item.source_references,
    supporting_document_ids: item.supporting_document_ids,
    support_state: item.support_state,
    price_note: item.priceNote,
    needs_review: item.needs_review,
    possible_matches: item.possibleMatches,
    price_options: item.priceOptions,
    wording_options: item.wording_options,
    source_wording: item.source_wording,
    proposed_category: item.proposed_category,
    category_ids: item.category_ids,
    primary_category_id: item.primary_category_id,
    description_origin: item.description_origin,
    review_status: item.review_status,
    provenance: item.provenance,
  };
}
function formatPrice(cents: number | null) { return cents == null ? "" : `$${(cents / 100).toFixed(2)}`; }
function parsePriceCents(value: string) { const normalized = value.trim().replace(/[ $,]/g, ""); if (!normalized || !/^\d+(?:\.\d{1,2})?$/.test(normalized)) return null; const [dollars, cents = ""] = normalized.split("."); return Number(dollars) * 100 + Number(`${cents}00`.slice(0, 2)); }
