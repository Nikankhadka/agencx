export interface KnowledgeSection {
  heading: string;
  body: string;
}

export interface PendingOffering {
  name: string;
  description: string;
  price_cents: number | null;
  sources: ("owner" | "document")[];
}

export type ReviewOffering = PendingOffering & { price_options?: number[] };

export interface KnowledgeRecord {
  id: string;
  filename: string;
  doc_type: string;
  status: string;
  error: string | null;
  sections: KnowledgeSection[];
  offering_candidates?: ReviewOffering[];
}

export function sourceLabel(record: KnowledgeRecord): string {
  if (!record.filename.startsWith("http")) return record.filename;
  try {
    return new URL(record.filename).host;
  } catch {
    return record.filename;
  }
}

export function statusLine(record: KnowledgeRecord): string {
  if (record.status === "draft") return "Not saved yet";
  if (record.status === "failed") return record.error ?? "Something went wrong";
  if (record.status === "ready") return "Answering from this";
  return "Working on it";
}
