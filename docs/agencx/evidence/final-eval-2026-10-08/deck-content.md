# Slide 10 content - Evaluation (Sabbaba demo tenant)

## Headline
45 of 51 measured customer turns fully correct, 0 failures, 0 hard fails. Every price came from the catalog or the pricing engine.

## Three numbers
- 88% PASS, 12% PARTIAL, 0% FAIL (51 measured turns, local run, post-fix build)
- Order totals exact: $39.80, $61.50, $19.90 computed by the pricing engine, never by the model
- Typical reply 3.8 s (p95 7.1 s); 67% within the 4 s target on a free-tier model

## What worked
- Prices and totals: no invented figure, unknown price (Caramel Cookie) honestly "not confirmed"
- Dietary and allergy questions: kitchen caveat carried, no unsafe "safe" claims
- Handoff: name and email captured once, conversation lands with the owner, no phone ask
- Multi-turn: context kept across 4 turns, no repeated greeting
- Resilience: a slow or failed provider call no longer kills the chat

## Before and after (said carefully)
Interim pre-fix run: 29 PASS / 16 PARTIAL / 22 FAIL of 67 valid turns, 6 critical. After seven targeted fixes: 45 / 6 / 0 of 51. Different, curated question set, so read it as "the fixes landed", not as a like-for-like accuracy gain.

## Honest limits (put on the slide or say aloud)
- Run locally; hosted latency not measured
- 11 turns, including all the adversarial guard tests, were blocked by the free-tier daily quota and will be re-run
- Single grader with founder re-grade pending (agreement rate: ____)
- Known gaps: allergen caveat occasionally dropped, a few prices spelled in words, thin recommendations

## Speaker note for a hard question
"The numbers cover realistic customer questions. The adversarial set hit the provider's free daily cap, and I report it as not measured rather than passed."

## Appendix test plan (one line each)
Groups A menu prices, B dietary, C shop info, D recommend, E order totals, F multi-turn, G handoff, H guards. 62 turns, 12 s apart, sequential, no retries; ground truth from the seed; labels PASS / PARTIAL / FAIL plus hard-fail list; founder blind re-grades about 20%.
