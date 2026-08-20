# Phase 3: Knowledge, Retrieval, Business Tab

**Calendar slot:** Week 2 (start) + Week 3 (finish)

## Goal

The owner can upload documents (menu, FAQs, rates, terms), the ingestion pipeline chunks and embeds them, and hybrid retrieval behind `get_business_context()` serves relevant chunks. The Business tab shows the profile and uploaded knowledge back to the owner for trust and correction. A golden retrieval set is seeded and recall@5 >= 0.85 is green.

## Features

### Knowledge

**Spec:** The owner uploads documents through the Chat tab (FileDropzone or paste). The ingestion pipeline extracts text, chunks (~400 tokens, 15% overlap, heading-aware), embeds (local bge-small in dev), and stores in `knowledge_chunks` with pgvector HNSW and GIN on tsvector. Hybrid retrieval combines dense + sparse + RRF (k=60) + cross-encoder rerank behind one `retrieve()`. `get_business_context(tenant_id, query)` is the single entry point - whole-corpus fast path when under token budget, hybrid retrieval above it. Both paths return the same shape (chunk id, content, source, `score`). Document status flows pending -> processing -> ready -> failed. Failed documents get a retry affordance.

**What this feature does not own:** the assistant graph (Phase 4), the public page (Phase 4), citations in chat replies (Phase 4).

**Design:** FileDropzone in the Chat tab accepts PDF, PNG/JPG, DOCX. Documents render as attachment chips with file-icon + filename. Per-file status shown in the Business tab's document table (pending/processing/ready/failed + retry on failed). The Business tab (S2, design.md) is the show-back surface.

**Stories:**

#### US-7 Upload document

**When:** The owner is in the Chat tab and wants to add knowledge.

**Happy path:**
1. The owner types a description ("here's my menu") and the "+" affordance opens a sheet with upload file.
2. The owner selects a PDF/PNG/DOCX file. The file appears as an attachment chip in the chat.
3. The ingestion pipeline extracts text and queues processing. The document status shows as `processing`.
4. On completion, the agent acknowledges in chat: "Got your menu - I'll answer from it now." The document status shows `ready`.

**Alternate paths:**
- Paste a URL: detected as a link on submit. The ingestion pipeline fetches and extracts the page.
- Multiple files in sequence: each gets its own attachment chip and status.

**Failure modes:**
- Unreadable file: "Couldn't read that one. Try a different file, or paste the text."
- Unsupported format: "That file type isn't supported yet. PDF, Word documents, and images work."
- Extraction timeout: document shows `failed` with retry affordance.

**Acceptance criteria:**
- [ ] FileDropzone accepts PDF, PNG/JPG, DOCX
- [ ] Uploaded file appears as attachment chip in chat
- [ ] Document status flows pending -> processing -> ready -> failed
- [ ] Failed documents get a retry affordance
- [ ] Paste URL detection works
- [ ] Agent acknowledges successful uploads conversationally

#### US-8 Chunk and embed pipeline

**When:** A document reaches `processing` status.

**Happy path:**
1. The ingestion pipeline extracts text from the document.
2. Text is chunked: ~400 tokens per chunk, 15% overlap between chunks, heading-aware splitting.
3. Each chunk is embedded (local bge-small in dev, configurable behind ModelPort) and stored in `knowledge_chunks` with the embedding vector and tsvector (generated from content).
4. HNSW and GIN indexes are created on the `knowledge_chunks` table.
5. On completion, document status moves to `ready`.

**Acceptance criteria:**
- [ ] Chunks are ~400 tokens with 15% overlap
- [ ] Embedding dimension follows the configured embedder
- [ ] tsvector is GENERATED ALWAYS AS STORED from content
- [ ] HNSW index on embedding (vector_cosine_ops)
- [ ] GIN index on tsvector
- [ ] Document status transitions atomically

#### US-9 Dense + sparse indexes

**When:** Chunks exist in `knowledge_chunks`.

**Happy path:**
1. Dense retrieval: pgvector HNSW similarity search on `embedding` column, scoped to `tenant_id`.
2. Sparse retrieval: Postgres FTS using `plainto_tsquery` against `tsv` column, scoped to `tenant_id`.
3. Both query paths include explicit `where tenant_id = :tenant_id` alongside RLS.

**Acceptance criteria:**
- [ ] Dense retrieval returns top-k by cosine similarity
- [ ] Sparse retrieval returns top-k by ts_rank
- [ ] Both paths scoped to tenant_id efficiently (index + predicate)

#### US-10 Fusion + rerank behind one retrieve()

**When:** Both dense and sparse results exist.

**Happy path:**
1. Reciprocal Rank Fusion (RRF) with k=60 combines dense and sparse results into a single ranked list.
2. A local cross-encoder reranks the fused list and returns top-k chunks with scores.
3. The `retrieve()` function is the single entry point.

**Acceptance criteria:**
- [ ] RRF k=60 combines dense + sparse results
- [ ] Cross-encoder rerank produces final ordering
- [ ] `retrieve()` returns (chunk_id, content, source, score)

#### US-11 get_business_context seam (two paths)

**When:** The assistant needs grounded context for a reply.

**Happy path:**
1. `get_business_context(tenant_id, query)` checks whether the tenant's whole corpus fits in the reply token budget (prompt + all chunks + draft < context window).
2. **Whole-corpus fast path:** if under budget, returns the full corpus directly. No retrieval scoring needed.
3. **Hybrid retrieval:** if over budget, runs dense+sparse+RRF+rerank and returns top-k chunks with citations.
4. Both paths return the same shape.

**Acceptance criteria:**
- [ ] Single entry point `get_business_context(tenant_id, query)`
- [ ] Whole-corpus path fires when corpus fits token budget
- [ ] Hybrid path fires when corpus exceeds budget
- [ ] Both paths return identical shape
- [ ] Token budget check is measured, not guessed

#### US-12 Golden retrieval set

**When:** Phase 3 retrieval is built.

**Happy path:**
1. Hand-labelled query-to-chunk pairs with negatives seeded into `eval_cases` (case_type `retrieval`).
2. At minimum: 20 positive cases (query with known-relevant chunk ids) and 10 negative cases (out-of-domain questions that must return nothing relevant).
3. `backend/evals/retrieval_eval.py` runs against the golden set and reports recall@5, recall@3, MRR, nDCG@5, and negative-set contamination.

**Acceptance criteria:**
- [ ] Golden set seeded with 20+ positive and 10+ negative cases
- [ ] recall@5 >= 0.85 (absolute gate)
- [ ] Negative-set contamination below the refusal threshold
- [ ] Retrieval eval runs deterministically (the reranker is local)

### Business Profile

**Spec:** The Business tab displays the profile and knowledge the owner gave the agent - the show-back surface. The owner sees their business name, business type, hours, services, and uploaded documents. Edits happen through the Copilot conversationally ("change my hours to 9-6"), which surfaces a confirmation card and updates the Business tab. The tab is not a settings tree: no configuration that exists only as a toggle. The thin exceptions in Stage 1 are a "live / not live" state indicator and the share link + QR code. Re-ingestion is supported: after profile changes, the owner can trigger re-processing of existing documents.

**What this feature does not own:** the onboarding interview (Phase 2), the Chat tab (Phase 2), knowledge ingestion (this phase, knowledge feature).

**Design:** The Business tab (S2, design.md) renders a two-section surface: profile section (business name, business type, hours, services as read-back cards) and documents section (table with filename, type, status, retry). Edits happen through the Copilot thread, not through inline form fields. The show-back updates in real time via SSE (`onboarding_beat_completed` event). Re-ingestion button appears alongside documents.

**Stories:**

#### US-13 Business tab show-back

**When:** The tenant has completed onboarding and the Business tab exists.

**Happy path:**
1. The Business tab renders the profile section: business name, business type, hours, and services as read-back cards.
2. The documents section renders a table with filename, doc_type, status (pending/processing/ready/failed), and a retry button on failed documents.
3. Empty state (no documents uploaded yet): prompt to upload through the Chat tab conversationally.
4. The live/not-live indicator shows whether the public page is active.

**Acceptance criteria:**
- [ ] Profile section shows all confirmed fields from onboarding
- [ ] Documents table shows per-file status with retry on failed
- [ ] Empty state for no documents with conversational prompt
- [ ] Live/not-live indicator
- [ ] No settings toggles anywhere on the tab
- [ ] The tab updates in real time when profile changes via the Copilot

#### US-14 Re-ingestion

**When:** The owner changes their profile in a way that affects document interpretation.

**Happy path:**
1. After a profile change (e.g. new hours, new service), the Business tab shows a "Re-process documents" affordance near the documents section.
2. Tapping it triggers re-ingestion of existing documents against the updated profile.
3. Documents go through the processing pipeline again. Status resets to `processing`.

**Acceptance criteria:**
- [ ] Re-ingestion affordance appears after profile changes
- [ ] Re-ingestion re-processes existing documents through the full pipeline
- [ ] Document status updates correctly

## Tickets

| Ticket | Name | What it delivers | Files/modules | Depends on |
|---|---|---|---|---|
| T-017 | Upload + extraction | File upload endpoint; text extraction from PDF/PNG/DOCX; URL fetch and extract; `documents` table writes; FileDropzone UI component | `backend/app/routes/upload.py`, `backend/app/services/extraction.py`, `frontend/src/components/FileDropzone.tsx`, `backend/migrations/0004_knowledge.sql` | T-011 |
| T-018 | Chunk + embed pipeline | Chunker (~400 tokens, 15% overlap, heading-aware); embedder (local bge-small via ModelPort); `knowledge_chunks` table writes | `backend/app/ingestion/chunker.py`, `backend/app/ingestion/embedder.py`, `backend/app/ingestion/pipeline.py` | T-017 |
| T-019 | Dense + sparse indexes | pgvector HNSW index creation and query; Postgres FTS GIN index creation and query; both scoped to tenant_id | `backend/app/retrieval/dense.py`, `backend/app/retrieval/sparse.py` | T-018 |
| T-020 | Fuse + rerank behind one retrieve() | RRF k=60 fusion; local cross-encoder rerank; `retrieve()` entry point | `backend/app/retrieval/fusion.py`, `backend/app/retrieval/rerank.py`, `backend/app/retrieval/service.py` | T-019 |
| T-021 | get_business_context seam | Token budget check; whole-corpus fast path; hybrid retrieval path; returns same shape for both | `backend/app/services/retrieval.py` | T-020 |
| T-022 | Golden retrieval set + eval | Hand-labelled eval cases seeded (20+ positive, 10+ negative); `retrieval_eval.py` reporting recall@5, recall@3, MRR, nDCG@5, negative-set contamination; recall@5 >= 0.85 gate | `backend/evals/retrieval_eval.py`, `backend/seeds/seed_eval_cases.py` | T-020 |
| T-023 | Business tab + re-ingestion | Business tab UI: profile show-back cards, documents table, live/not-live indicator, re-ingestion affordance; SSE integration for real-time updates | `frontend/src/app/business/`, `frontend/src/components/BusinessProfile.tsx`, `frontend/src/components/DocumentTable.tsx`, `backend/app/routes/business.py` | T-016, T-021 |

## Gate

- [ ] A document upload completes the full pipeline: upload -> extract -> chunk -> embed -> store -> ready
- [ ] `get_business_context(tenant_id, query)` returns relevant chunks; whole-corpus fast path works for small corpora
- [ ] Golden retrieval set is seeded; recall@5 >= 0.85 is met (absolute gate)
- [ ] Business tab renders profile show-back and document table with correct status
- [ ] Failed documents show retry affordance
- [ ] Re-ingestion works after profile changes

## Done when

- [ ] Seven tickets complete
- [ ] Full ingestion pipeline works end-to-end for PDF, PNG, DOCX, and URL
- [ ] `retrieve()` returns correct chunks; whole-corpus path and hybrid path both verified
- [ ] recall@5 >= 0.85 on the golden set
- [ ] Business tab shows correct profile and document states
- [ ] Edit-via-Copilot flow updates the Business tab in real time
- [ ] Fits or observed slip
