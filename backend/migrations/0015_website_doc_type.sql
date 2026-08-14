-- 0015_website_doc_type.sql - allow 'website' documents (URL ingestion, T-056).

alter table documents drop constraint documents_doc_type_check;
alter table documents add constraint documents_doc_type_check
  check (doc_type in ('policy', 'faq', 'catalog', 'price_list', 'other', 'website'));
