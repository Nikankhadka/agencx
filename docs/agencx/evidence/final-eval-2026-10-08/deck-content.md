# Slide 10 content - Evaluation (Sabbaba demo tenant)

## Headline
54 of 62 customer turns fully correct, 0 failures, 0 hard fails. Every price came from the catalog or the pricing engine.

## Three numbers
- 87% PASS, 13% PARTIAL, 0% FAIL (62 turns, local run, post-fix build)
- Order totals exact: $39.80, $61.50, $19.90 computed by the pricing engine, never by the model
- Typical reply 3.8 s (p95 7.1 s); 69% within the 4 s target on a free-tier model

## What worked
- Prices and totals: no invented figure, unknown price (Caramel Cookie) honestly "not confirmed"
- Dietary and allergy questions: kitchen caveat carried, no unsafe "safe" claims
- Handoff: name and email captured once, conversation lands with the owner, no phone ask
- Multi-turn: context kept across 4 turns, no repeated greeting
- Resilience: a slow or failed provider call no longer kills the chat
- Guards: prompt-injection, other-business, off-topic, "are you a robot" and invented-calories prompts all handled (one sample each)

## Before and after (said carefully)
Interim pre-fix run: 29 PASS / 16 PARTIAL / 22 FAIL of 67 valid turns, 6 critical. After seven targeted fixes: 54 / 8 / 0 of 62. Different, curated question set, so read it as "the fixes landed", not as a like-for-like accuracy gain.

## Honest limits (put on the slide or say aloud)
- Run locally; hosted latency not measured
- Guard prompts run once each, on a second API key after the free daily quota ran out
- Single grader with founder re-grade pending (agreement rate: ____)
- Known gaps: the assistant twice stated an unsourced "we don't do that" (discounts, cooking classes), allergen caveat occasionally dropped, a few prices spelled in words, thin recommendations

## Speaker note for a hard question
"The set is curated toward realistic customer questions plus a small guard set. The two partials in the guard and discount questions are the assistant claiming a negative it had no source for, and I report them."

## Appendix test plan (one line each)
Groups A menu prices, B dietary, C shop info, D recommend, E order totals, F multi-turn, G handoff, H guards. 62 turns, 12 s apart, sequential, no retries; ground truth from the seed; labels PASS / PARTIAL / FAIL plus hard-fail list; founder blind re-grades about 20%.
