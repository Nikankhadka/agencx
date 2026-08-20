# Stage 2 Backlog

Deferred features from Stage 2. One paragraph per feature, why it is deferred, and the hard contracts already decided so they are not re-derived from scratch. Not planned or ticketed until Stage 1 reports back.

## Deferred features

### Lead capture

When a customer asks something that crosses from "question about the business" into "I want to hire you", the assistant captures name, contact, service needed, timing, and location into a lead record. Deferred because lead records are valueless before the assistant can hold a grounded conversation - the Stage 1 bet comes first.

### Quoting

The Quote Agent selects pricing rules and quantities; the deterministic pricing engine computes totals in integer cents and surfaces a QuoteCard for owner approval. Deferred because the pricing engine is expensive to build before the grounded-conversation bet is proven.

### Payments

Platform-collected payments via provider (PLATFORM mode), manual mark-paid (DIRECT mode), deferred collection (DEFERRED mode). Payouts, payment intents, and webhook reconciliation. Deferred because payments require KYC, provider integration, and a whole class of compliance - all of which need Stage 1 to validate demand first.

### Scheduling

The deterministic slot service computes availability; calendar sync (write-only first, two-way post-validation). Deferred because scheduling is only useful when there are jobs to schedule, and jobs are Stage 2.

### Invoicing

Write-once tax invoices composed from deterministic engine output. Three document types forked on `has_abn` and `is_gst_registered`. Five-year retention. Deferred because invoices are only useful when there are completed jobs to bill.

### Post-job care

Review drafts, rebooking prompts, customer follow-up cadences. Deferred because it depends on completed jobs (Stage 2 quotes+scheduling+payments).

### Team members

The Jordan persona: second+ person on a tenant, role-based permissions (`owner`/`staff`), team inbox. Deferred because customer proof precedes team proof - Stage 1 validates the solo operator use case first.

### Channels (SMS, embed, voice)

Beyond the native public page chat: SMS via real provider (not MockSmsAdapter), lead-capture embed for the tenant's own website, voice handling. Deferred because each channel adds a paid dependency (SMS) or significant infra (voice), and the public page validates the channel concept first.

## Contracts already decided

### Write-once invoicing (I7)

Issued invoices are immutable. Corrections are credit notes. Records retain for at least five years in a format the ATO can access (rendered PDF or equivalent, not just database rows). Never model-touched (I1).

### Payment idempotency (I6)

Manual mark-paid and provider webhooks are idempotent against the same payment. Double-counted revenue is a hard failure. Idempotency keys on every payment intent.

### Payment modes

Three modes: `PLATFORM` / `DIRECT` / `DEFERRED` (decision 8, never the old brand name). Keep the `payment_processing_mode` column and `payment_processing_mode_snapshot` in the spine even though only DIRECT is built in Stage 1. Stripping mode-awareness to "simplify" is the one shortcut that forces a rewrite later.

### ATO compliance rules (from research/au-compliance.md)

1. **Tax invoice requirements:** seller identity, ABN, date of issue, description of items with quantity and price, GST amount (shown separately or stated as total including GST), extent of taxable sale. All seven fields are deterministic (I1).
2. **The $1,000 rule:** for sales exceeding $1,000 including GST, the invoice must carry the buyer's identity or ABN. Captured at quote time, not invoice time.
3. **ABN and no-ABN withholding:** an invoice for a taxable sale without an ABN may force the payer to withhold 47%. This is why document type forks deterministically off `has_abn` and `is_gst_registered`.
4. **GST registration threshold:** $75,000 annual turnover. The Advisor monitors the rolling 12-month figure and raises a compliance signal on approach.

Sources: ATO invoice requirements, Sprintlaw, Lawpath, Reckon (see archived research/au-compliance.md for links).

### Privacy Act: build to full APP compliance

The small-business exemption ($3 million turnover or less) is legislated to expire December 2026. Build to full Australian Privacy Principles compliance from the start: data minimisation, deletion on account closure, no cross-tenant referencing of customer content, access control. These are architectural properties - retrofitting means touching every table.

### Stage 2 table names

`catalog_items`, `pricing_rules`, `quotes` + `quote_line_items`, `invoices`, `credit_notes`, `payments`, `refunds`, `approvals`, `jobs` + `recurring_series`, `events`, `i_dont_know_classifications`, `inbound_communications`, `tenant_tax_profiles`. Full column specs live in their Stage 2 feature builds, not here.

## Open questions

| # | Question | Owned by | Open until |
|---|---|---|---|
| 1 | University deliverable: deadline and required hand-ins (must shape phase gates) | architecture.md | known, then it writes the calendar |
| 2 | Frontend host: Cloudflare Pages (`next-on-pages`) vs paid Vercel | architecture.md | Phase 5 ticket (decision 10) |
| 3 | Embedding + rerank provider when the golden set exceeds the local budget | architecture.md | Phase 3 golden set |
| 4 | Settings shape if Stage 2 ever justifies a toggle row | prd.md | Stage 2 planning |
| 5 | Model provider on the customers' side (free tiers rotate monthly) | architecture.md | each phase boundary |
| 6 | SMS lead notification: provider for the first real inbound lead | this document | Stage 2 |
