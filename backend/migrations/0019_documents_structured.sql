-- 0019_documents_structured.sql - O-3 knowledge screen: a document the owner
-- reads before it answers anything.

-- Ingest now has a review step. A source is extracted and processed into
-- readable sections, and stays 'draft' - no chunks, so retrieval cannot see it -
-- until the owner saves it. Saving runs the existing pipeline and lands it
-- 'ready' exactly as before.
alter table documents drop constraint documents_status_check;
alter table documents add constraint documents_status_check
  check (status in ('draft', 'pending', 'processing', 'ready', 'failed'));

-- The readable form: [{"heading": ..., "body": ...}], the owner's edits
-- included. Null on rows ingested before this, which are structured on first
-- view rather than backfilled - the work needs a model call per document and
-- nothing reads the column until someone opens the screen.
alter table documents add column structured jsonb;
