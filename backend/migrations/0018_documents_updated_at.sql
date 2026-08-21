-- 0018_documents_updated_at.sql - P-4: knowledge_version needs a document
-- timestamp that moves.

-- ``uploaded_at`` is insert-only, so a re-ingest (retry button, URL re-scrape)
-- left the row's only timestamp untouched - invisible to any cache keyed on it.
-- ``updated_at`` plus the shared touch trigger (0001) fixes that for free: the
-- pipeline already writes status 'processing' then 'ready' on every (re-)ingest,
-- and each of those updates now bumps the stamp.
alter table documents add column updated_at timestamptz not null default now();
create trigger documents_touch before update on documents
  for each row execute function touch_updated_at();
