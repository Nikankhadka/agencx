/**
 * The knowledge screen's wire types, mirroring `KnowledgeRecord` in
 * app/features/knowledge/api.py. A record is one source - a file or a page -
 * held as the readable sections its owner reviews and edits.
 */

export interface KnowledgeSection {
  heading: string;
  body: string;
}

export interface OfferingCandidate {
  name: string;
  price: string | null;
  price_cents: number | null;
}

export interface KnowledgeRecord {
  id: string;
  filename: string;
  doc_type: string;
  /** draft = read but not answering yet; ready = live; failed = ingest failed. */
  status: string;
  error: string | null;
  sections: KnowledgeSection[];
  offering_candidates?: OfferingCandidate[];
}

/** A link is shown by its host; a file by its name. */
export function sourceLabel(record: KnowledgeRecord): string {
  if (!record.filename.startsWith("http")) return record.filename;
  try {
    return new URL(record.filename).host;
  } catch {
    return record.filename;
  }
}

/** One quiet line saying where this record stands, in the owner's terms. */
export function statusLine(record: KnowledgeRecord): string {
  if (record.status === "draft") return "Not saved yet";
  if (record.status === "failed") return record.error ?? "Something went wrong";
  if (record.status === "ready") return "Answering from this";
  return "Working on it";
}
