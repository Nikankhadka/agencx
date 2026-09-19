# Owner input and conversational-agent architecture

## Research question

How should Agencx interpret open-ended owner input without forcing confirmation
after every answer, and how do enterprise text and voice agents handle extraction,
ambiguity, validation, confirmation, workflow execution, and human handoff?

This note uses the public, first-party material linked below and the current
Agencx codebase. Sierra and Decagon do not publish enough detail to verify their
exact internal state machines, model routing, confidence thresholds, or database
schemas. Their sections below report only what those companies publicly document.
The Agencx recommendations are inferences from those public patterns, not claims
about proprietary internals.

## Conclusion

Enterprise conversational systems do not make a model the authority over stored
facts or business actions. They use a hybrid architecture:

```text
text or voice channel
        |
        v
literal user turn + channel metadata
        |
        v
probabilistic intent/entity proposal
        |
        v
typed conversation state + deterministic validation
        |
        v
risk and ambiguity policy
   |          |             |
 commit    clarify       explicit confirm
   |          |             |
   +----------+-------------+
              |
              v
deterministic tool or database action
              |
              v
verified result + response + trace
              |
              +----> bounded recovery or human handoff
```

The right Agencx direction is therefore:

1. Preserve the owner's literal wording as evidence.
2. Let the model propose structured meaning, but let code validate and commit it.
3. Use implicit read-back for normal, low-risk captures.
4. Use explicit `Yes` and `No` only for unique, ambiguous, sensitive, or
   consequential values and actions.
5. Make `No` a deterministic correction transition with no model call. The next
   typed replacement can enter the ordinary extraction path.
6. Keep broad offering families in the existing profile-level `services` fact.
   Create catalog offering rows only for distinct items or services that the
   business actually sells. Use the existing per-row `offerings.category` to group
   those rows.

This preserves the capability demonstration: the owner speaks naturally and the
system normally moves forward. Confirmation appears where a wrong interpretation
has a meaningful cost, not as a tax on every turn.

## What public enterprise systems verify

### Structured state sits between language and action

Dialogflow CX models collected information as typed parameters, including list
parameters, and tracks whether required parameters are filled. It supports
parameter-level no-match and no-input handlers, plus transitions after repeated
failures. A webhook can mark a parameter `INVALID`, clear it, and trigger a
reprompt. [Dialogflow CX parameters](https://docs.cloud.google.com/dialogflow/cx/docs/concept/parameter)
and [Dialogflow CX webhook validation](https://docs.cloud.google.com/dialogflow/cx/docs/how/webhook)
document that boundary.

Amazon Lex uses intents and typed slots, lets Lambda apply business validation,
tracks retry attempts, and exposes explicit conversation states such as slot
elicitation, intent confirmation, fulfillment, and failure. It can invoke a
fallback after ambiguous or repeatedly invalid input. [Amazon Lex slots](https://docs.aws.amazon.com/lexv2/latest/dg/intent-slots.html),
[conversation states](https://docs.aws.amazon.com/lexv2/latest/dg/managing-conversations.html),
and [fallback behavior](https://docs.aws.amazon.com/lexv2/latest/dg/built-in-intent-fallback.html)
show the pattern.

Rasa documents both entity-based and LLM-based slot filling, with deterministic
slot validation that rejects a value before the flow proceeds. Its priority rules
also allow conventional NLU extraction to win over an LLM proposal when both are
present. [Rasa slots](https://rasa.com/docs/reference/primitives/slots/) describes
the approach.

The consistent boundary is: language understanding proposes state; the workflow
owns accepted state and the next transition.

### Confirmation is selective

Google's conversation-design guidance distinguishes three treatments:

- implicit confirmation for most parameters;
- no confirmation for low-risk, reliably recognized values;
- explicit confirmation for high-cost misunderstandings such as names,
  addresses, messages sent on the user's behalf, transactions, and destructive
  actions.

It also recommends one-step correction after a read-back. [Google confirmation
guidance](https://developers.google.com/assistant/conversation-design/confirmations)
is the clearest public statement of this risk-based policy.

Lex makes confirmation a separate state and records confirmed or denied outcomes;
it does not require confirmation for every captured slot. [Lex confirmation
response format](https://docs.aws.amazon.com/lexv2/latest/dg/lambda-response-format.html)
documents the explicit `yes` or `no` transition.

The practical policy is not "confirm whenever an LLM was used." It is "confirm
when uncertainty or consequence makes silent acceptance unsafe." Privacy is a
separate concern: sensitive parameters may need redaction and minimal echoing,
not more spoken repetition. Dialogflow, for example, supports parameter-level log
redaction in its [parameter model](https://docs.cloud.google.com/dialogflow/cx/docs/concept/parameter).

### Sierra and Decagon publicly describe hybrid control

Sierra says its Agent SDK combines goals and guardrails with composable skills
such as triage, respond, and confirm, and lets a workflow vary its degree of
creativity and determinism. It also exposes simulation, logic traces, secure
actions, and contact-center handoff with a generated summary. [Sierra Agent
SDK](https://sierra.ai/uk/product/agent-sdk) documents those product-level
capabilities. Sierra separately states that procedural knowledge and deterministic
guardrails are declared outside the underlying model so consequential business
rules remain enforced. [Sierra's agent development life cycle](https://sierra.ai/blog/agent-development-life-cycle)
describes that design.

Decagon says Agent Operating Procedures combine natural-language workflow
definition with code, shared guardrails, execution traces, testing, and versioning.
[Decagon AOPs](https://decagon.ai/product/aop) describes the product contract.
Decagon also publicly describes a network of specialized models for intent,
workflow execution, hallucination detection, and escalation rather than one
monolithic model. [Decagon's model architecture](https://decagon.ai/blog/fine-tuning-ai-agents)
is evidence for that statement.

These sources verify the control pattern, but not the vendors' private schemas or
algorithms. A claim that either vendor uses a particular pending-field table,
classifier threshold, or prompt would be speculation.

### Voice adds a channel layer, not a different truth model

Traditional voice systems add voice activity detection, turn detection, speech
recognition, and speech synthesis around the agent logic. Decagon describes the
common cascade as STT, agent logic, and TTS, and reports that premature turn
boundaries can corrupt the input before reasoning begins. [Decagon's VAD
research](https://decagon.ai/blog/bayesian-vad) separates turn-boundary quality
from transcription quality.

Dialogflow exposes end-of-speech sensitivity, smart endpointing, no-speech
timeouts, and barge-in. On barge-in it stops response audio and processes the new
user input. [Dialogflow advanced speech settings](https://docs.cloud.google.com/dialogflow/cx/docs/concept/advanced-speech)
documents those controls.

Newer full-duplex systems can combine listening and speaking in one model, but
they still separate real-time media from deeper reasoning, tools, and business
logic. OpenAI describes a dedicated media path with asynchronous reasoning and
tool use in [its full-duplex architecture](https://openai.com/index/continuous-voice-interaction-with-gpt-live/).

Therefore, a voice agent is not inherently better at deciding whether "coffee"
is a category or an item. It may capture a more natural utterance, handle pauses,
and support interruption, but the same structured interpretation, validation,
confirmation, and action policy remains necessary behind the channel.

### Recovery and handoff are designed outcomes

Dialogflow supports a symbolic human-escalation transition for telephony
handoff. [Dialogflow CX handoff](https://docs.cloud.google.com/gemini-enterprise-cx/agent-assist/handoff-cx)
documents the event. Sierra advertises routing plus a detailed conversation
summary, while Decagon describes concise-summary voice transfer and guardrails
for escalation. [Sierra Agent SDK](https://sierra.ai/uk/product/agent-sdk) and
[Decagon Voice](https://decagon.ai/product/voice) provide the first-party claims.

The useful enterprise pattern is bounded recovery: one focused clarification,
one retry when appropriate, then either defer the field or hand off with structured
context. Infinite re-asking is not intelligence.

## Current Agencx architecture

Agencx already implements much of the hybrid pattern:

- A model produces a typed `DraftUpdate` containing profile fields, offering
  names, corrections, offering operations, and an `answered_asked` judgment.
  [The extraction contract](../../../backend/app/onboarding/flow.py#L111) makes
  the model a structured proposer rather than a direct database writer.
- The server owns the beat order and the question shown next. The response model
  writes only a short acknowledgment. [The extraction prompt](../../../backend/app/onboarding/agent.py#L179)
  and [progress function](../../../backend/app/onboarding/agent.py#L642) show the
  split.
- Each beat can apply a deterministic plausibility check. The model's
  `answered_asked` result and the beat validator can each veto a capture.
  [Beat validation](../../../backend/app/onboarding/beats.py#L132) and [the
  rejection path](../../../backend/app/onboarding/agent.py#L1041) implement it.
- Owner and business names become durable pending proposals and do not reach the
  authoritative draft until the owner confirms. [Pending-name state](../../../backend/app/onboarding/agent.py#L283)
  and [name confirmation handling](../../../backend/app/onboarding/agent.py#L963)
  implement that safety boundary.
- Fixed chips, including assistant voice selection, bypass the model and use a
  deterministic selection endpoint. [Selection handling](../../../backend/app/features/onboarding/controller.py#L260)
  implements it.
- Repeated failures are bounded by the beat cursor and attempt count instead of
  looping forever.

Two gaps explain the reported experience:

1. The name confirmation input declares only a `Yes` chip. Typing another value
   is the current correction route. [The input specification](../../../backend/app/onboarding/beats.py#L434)
   confirms the missing `No` affordance.
2. The offering extractor asks for `offering_names` when the owner explicitly
   names individual offerings, but it also instructs the model to split a run-on
   list into separate entries. Those entries immediately become pending offering
   candidates, and the same list may populate `profile.services`.
   [Offering extraction rules](../../../backend/app/onboarding/agent.py#L197) and
   [candidate merge behavior](../../../backend/app/onboarding/agent.py#L1008)
   show the overlap.

The document-import path already applies a stricter distinction: category tags
and headings are not sellable items unless the group has its own price.
[Document offering extraction](../../../backend/app/features/knowledge/offering_extraction.py#L210)
contains that rule. Owner-typed extraction should align with the same domain
meaning.

## Category versus offering in the current domain model

The category idea does not require a new category table for the stated use case.
The effective schema already adds `category` to each offering row.
[Migration 0025](../../../backend/migrations/0025_schema_cleanup.sql#L159) adds
the column, and [offering persistence](../../../backend/app/features/business/service.py#L122)
stores either an owner-supplied category or a model suggestion. The public
storefront reads `profile.services` separately from categorized offering rows.
[Storefront loading](../../../backend/app/features/business/service.py#L515)
shows both outputs.

The current pending candidate model does not include a category field.
[PendingOffering](../../../backend/app/onboarding/flow.py#L140) carries a name,
description, price evidence, source provenance, and review metadata, but no
category. Category assignment therefore happens only when rows are created or
edited later.

Use these meanings:

| Owner wording | Store now | Catalog consequence |
|---|---|---|
| "We offer meats, desserts, coffee, and salads" | Preserve the phrase in `profile.services`; optionally keep the parsed family labels as a pending interpretation | Do not invent product rows |
| "We sell lamb shoulder, beef ribs, and chicken skewers" | Three offering candidates | Each becomes a row after review; a category such as `Meats` may group them |
| "Flat white is $5" | One offering candidate with source-backed price handling | A `Flat white` row, potentially under `Coffee` |
| "We offer coffee" | Ambiguous | Keep it as a broad service by default, or ask one focused question later if item-level catalog behavior is required |

A category groups offering rows. It is not itself proof that a distinct item is
sold. An empty category also has no current storefront representation because
categories are derived from offering rows. If the product later needs standalone
category pages before any items exist, that would be a separate domain-model
decision and could justify a category entity. It is not required for this
onboarding refinement.

## Offering normalization and catalog semantics

Normalization is not one operation. A production catalog separates four
decisions that are easy to accidentally collapse into one model prompt:

1. **Canonical naming:** what the owner wants customers to see.
2. **Entity resolution:** whether two mentions refer to the same stored thing.
3. **Taxonomy assignment:** which group or external classification the thing
   belongs to.
4. **Description generation:** optional prose derived from accepted facts.

Each has a different authority and failure mode. A normalized string can help
find a record, but it should not become its display name, decide its category, or
authorize generated claims about it.

### Canonical naming belongs to the tenant

The canonical customer-facing name should be the owner's approved wording, with
its spelling, case, and meaningful punctuation preserved. Identity should use an
immutable internal ID, plus an external SKU or source identifier when one exists.
Google Merchant Center similarly separates a stable product `id` from its
customer-facing `title`, and recommends that the title match the merchant's
landing page. [Google's product data specification](https://support.google.com/merchants/answer/7052112?hl=en)
documents that split. Schema.org likewise provides separate `name`, `sku`,
`identifier`, `alternateName`, and `category` properties for a
[Product](https://schema.org/Product), including a service sold by a business.

Agencx currently preserves the submitted offering name, but also treats an
NFKC-normalized, case-folded, punctuation-stripped string as the shared equality
key at every offering boundary. [The current normalizer](../../../backend/app/features/business/offering_candidates.py#L21)
is a useful candidate-retrieval key, not proof of identity. Unicode explicitly
distinguishes compatibility normalization from merely preserving composed text,
and warns that compatibility normalization can erase distinctions.
[Unicode Normalization Forms](https://www.unicode.org/reports/tr15/) provides the
standard. Removing all punctuation adds further possible collisions, such as a
model code whose punctuation is significant.

The durable shape should therefore remain conceptually separate:

```text
offering.id                  stable identity
offering.name                owner-approved display value
derived normalized key       tenant-scoped candidate lookup only
aliases and source text      provenance, not replacement display values
external identifiers         optional strong identity evidence
```

### Entity resolution is a staged matching problem

AWS Entity Resolution normalizes fields before rule-based or ML matching, then
assigns match identifiers and, for ML workflows, confidence levels. It supports
exact rules, fuzzy rules, and chained workflows rather than claiming that string
cleanup alone establishes identity. [AWS Entity Resolution](https://docs.aws.amazon.com/entityresolution/latest/userguide/what-is-service.html)
and its [matching-workflow guidance](https://docs.aws.amazon.com/entityresolution/latest/userguide/create-matching-workflow.html)
document this separation. OpenRefine's official reconciliation model similarly
returns typed candidates and scores, preserves the original string, and leaves
unclear matches for human judgment. [OpenRefine reconciliation](https://openrefine.org/docs/manual/reconciling)
describes that workflow.

For Agencx, matching should be tenant-scoped and ordered by evidence:

1. Reuse the known offering ID or trusted source identifier deterministically.
2. Use the normalized name to retrieve possible matches within the tenant.
3. Auto-resolve only when the product rule makes the match unambiguous, such as
   an exact repeat from the same source with compatible structured attributes.
4. Treat punctuation collisions, fuzzy text, semantic similarity, and conflicting
   attributes as `possible_matches`; never let the model silently merge them.
5. Preserve the raw owner phrase and the chosen entity ID after resolution.

This is consistent with the existing `PendingOffering.possible_matches` rule,
which requires the owner to keep or combine near matches explicitly.
[Pending offering state](../../../backend/app/onboarding/flow.py#L140) already has
that safer review boundary. The current shared normalized key is suitable for
blocking candidates, but using it as the sole equality authority is stronger than
the evidence supports in a domain-agnostic system.

### Standard taxonomy and tenant vocabulary are complementary

There is no useful universal dictionary that can replace each business's
language. Major catalog systems keep both layers:

- Google has a predefined `google_product_category`, but separately supports the
  merchant-defined `product_type` when the merchant needs its own organization.
  [Google product categories](https://support.google.com/merchants/answer/6324436?hl=en)
  explains the distinction.
- Shopify gives a product one standard category from the Shopify Product Taxonomy
  and a separate custom product type unique to the merchant.
  [Shopify product categories](https://help.shopify.com/en/manual/products/details/product-category)
  documents the two fields, while its
  [public taxonomy](https://shopify.github.io/product-taxonomy/) provides stable
  categories, attributes, and values for interoperability.
- GS1 Global Product Classification supplies a shared segment, family, class,
  brick, and attribute hierarchy for trading partners.
  [GS1 GPC](https://www.gs1.org/standards/gpc/how-gpc-works) documents that purpose.

The industry pattern is therefore tenant vocabulary as the operational source of
truth, with an optional mapping to a published taxonomy when search, tax,
marketplace export, reporting, or partner interoperability requires it. A mapping
should store the taxonomy scheme, version, and stable code. It must not overwrite
the owner's label.

For ordinary Agencx categorization, constrain the model to existing tenant
categories and a typed escape hatch such as `new_label` or `null`. The current
category helper already prefers existing labels and returns `null` when uncertain,
but its result is still unconstrained free text.
[The category suggestion boundary](../../../backend/app/features/business/service.py#L30)
shows the current behavior. A future refinement should return an existing category
label where possible and stage a genuinely new label for owner review. If
categories later gain their own stable IDs, return that ID instead. It should not
use a global synonym dictionary to rename `Meats`, `Coffee`, or any other
owner-selected grouping.

### A category table is warranted only when category has its own lifecycle

Keep the current nullable `offerings.category` text while a category is only a
single grouping label derived from existing offerings. A normalized category
entity becomes justified when one or more of these become real product needs:

- stable category identity across renames and aliases;
- hierarchy, ordering, translations, media, descriptions, or policies owned by
  the category itself;
- empty categories that must exist before any offering belongs to them;
- multiple categories per offering;
- explicit category merge and deduplication workflows;
- versioned mappings to Shopify, Google, GS1, or another external taxonomy.

At that point, use a tenant-scoped category table and a stable foreign key, plus a
join table if membership becomes many-to-many. Until then, a new table would add
identity and lifecycle rules that the current product does not use. Broad service
families still belong in `profile.services`; actual sellable or bookable items
remain offering rows whose optional text category groups them.

### AI-generated descriptions are drafts, not normalized facts

Shopify calls AI-generated descriptions suggestions, warns that generated copy
can invent benefits or facts not supplied by the merchant, and requires the
merchant to review accuracy before publication.
[Shopify Magic product descriptions](https://help.shopify.com/en/manual/products/details/product-descriptions/shopify-magic)
documents those limits. Google also distinguishes algorithmically generated
titles and descriptions with structured provenance in its
[product data specification](https://support.google.com/merchants/answer/7052112?hl=en).

Agencx should generate description copy only from accepted structured facts and
retained source evidence. Generated copy should carry provenance, remain a draft
until owner approval, and produce no unsupported ingredients, specifications,
benefits, availability, or regulatory claims. It must never create a new offering
or a price. If the evidence is insufficient, the correct output is empty or a
request for the missing fact, not plausible-sounding completion.

## Recommended Agencx policy

### Capture policy

Classify each extracted mention as `broad_service`, `offering_item`, or
`ambiguous`, while preserving the literal owner phrase and source turn. This is
an interpretation proposal, not a stored fact by itself.

- `broad_service`: store in `profile.services`; create no offering row.
- `offering_item`: add a reviewable offering candidate; infer no child items,
  descriptions, or prices.
- `ambiguous`: keep the literal phrase in services and do not create a catalog
  row unless later evidence resolves it. Ask a focused clarification only when
  downstream behavior requires the distinction.

This policy treats "varieties of meat" as a broad family, not an item named
`Meat`. It also avoids pretending that a classifier can always resolve a word
such as `Coffee`, which may denote a category or an actual menu item.

### Confirmation policy

| Situation | Treatment |
|---|---|
| Fixed chip or deterministically validated low-risk field | Commit without another confirmation |
| Normal free-text profile capture | Implicit read-back while moving to the next beat; allow correction from any beat |
| Owner name or business name | Explicit `Yes` and `No` |
| Low-confidence or materially ambiguous interpretation | One focused clarification or explicit confirmation |
| Irreversible, public, monetary, security-sensitive, or externally visible action | Explicit confirmation or approval before execution |
| Known-invalid input | Explain the field-specific problem and re-ask; do not offer confirmation |

Do not rely only on a model's self-reported confidence. Use deterministic risk
rules, recognized ambiguity, validator outcomes, and channel evidence such as
speech-recognition confidence. A confidence number can inform the decision, but
it is not the authority.

### `No` interaction

The requested `No` behavior fits the architecture:

1. Do not call the model when the owner taps `No`.
2. Hide the confirmation chips and focus the existing composer.
3. Keep the rejected proposal available as evidence until a replacement is
   submitted or the owner leaves the field unresolved.
4. Send the replacement text through the ordinary extraction and validation
   path, then show the new proposal.

If correction mode must survive refresh, persist a deterministic state transition
such as `pending_name.status = "correcting"`. If refresh may show the confirmation
again, the UI transition can remain client-local. That is a product-state choice,
not an LLM decision.

## Comparison checklist for another application

Use this checklist while observing the other product:

1. Does it preserve a transcript or literal value separately from the normalized
   value?
2. Can one utterance fill multiple fields or list values without extra prompts?
3. Does it read normal captures back implicitly, or stop for explicit approval?
4. Which facts trigger explicit confirmation: names, addresses, identifiers,
   money, public copy, or irreversible actions?
5. Does `No` reopen input immediately, and does that action avoid a model call?
6. Can the user correct an earlier field from a later turn without restarting?
7. What happens after one or two failed interpretations?
8. In voice, can the user interrupt, pause mid-number, spell a proper noun, or
   recover from a bad transcript?
9. Are tool actions validated against a system of record, or does model prose
   count as completion?
10. Does human handoff carry the transcript, structured state, evidence, actions
    attempted, and unresolved question?
11. Can operators inspect traces and turn failures into regression tests?

The visible smoothness of an enterprise agent comes from this hidden structure.
The model handles variation in language; code controls state, truth, risk, and
actions.
