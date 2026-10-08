# sababa2 - faithfulness, answer relevancy and trajectory (2026-10-08)

Local build, tenant `sababa2` (fast path, whole corpus in context). Judge and model: Gemini `gemini-3.5-flash-lite`. The scorers are the project's own (`backend/evals/generation_eval.py`, `trajectory_eval.py`), driven by `backend/evals/sababa2_quality_eval.py`. Raw output: `data/sababa2-quality-rag.json` and `data/sababa2-quality-trajectory.json`.

## Headline

| Metric | Result | Project gate | Verdict |
|---|---|---|---|
| Faithfulness (24 served replies, 74 claims) | **0.90** (reply mean 0.899, claim level 67/74 = 0.905) | 0.85 | pass |
| Answer relevancy (same 24 replies) | **0.80** mean, 0.83 median, 9 of 24 at or above 0.85 | 0.85 | below gate |
| Trajectory tool correctness (11 cases) | **0.64** (7 of 11) | 0.90 | below gate, see the quoting note |
| Trajectory step efficiency | 1.00 (every case at its minimum step count) | - | - |

Nothing here was tuned or filtered after scoring. The 24-reply sample and the 11 cases were fixed before the first score (`backend/evals/datasets/sababa2_quality_sample.jsonl`, `sababa2_trajectory.jsonl`).

## Method

- **Faithfulness.** Each served reply is split into claims; a judge marks each claim supported or not against the tenant's own material (owner text, profile, offerings, retrieved chunks). Score = supported claims / claims.
- **Answer relevancy.** The judge writes 3 questions the reply would answer; the score is their mean cosine similarity to the real customer question (local embeddings). It rewards replies that restate the question and penalises short, correct replies and honest "not listed" replies.
- **Sample.** First turn of 24 distinct recorded cases from rounds 1 and 2, groups: menu_prices 4, prices 3, info 5, dietary 5, recommend 3, unsourced_negative 4. Handoff turns and engine-total turns are excluded here because they are graded in the main report.
- **Trajectory.** The real graph is driven on 11 golden tasks and scored on route, expected selections, terminal state and steps.

## Faithfulness by group

| Group | Replies | Faithfulness | Relevancy |
|---|---|---|---|
| menu_prices | 4 | 1.00 | 0.93 |
| prices | 3 | 1.00 | 0.83 |
| dietary | 5 | 0.93 | 0.85 |
| recommend | 3 | 0.92 | 0.62 |
| info | 5 | 0.90 | 0.74 |
| unsourced_negative | 4 | 0.67 | 0.80 |

19 of 24 replies scored a perfect 1.0. The 5 below 1.0 hold 7 unsupported claims:

| Case | Question | Judge's unsupported claim | My read (a human judgement, not the metric) |
|---|---|---|---|
| R-C1 | Is there parking nearby? | "Shopping centre parking is typically available nearby." | **Real.** An unsourced generalisation. This is the known unsourced-negative weakness (fix offered in the main report, C.2). |
| B5 | Milk allergy, is the falafel plate dairy free? | "Contains no animal products", "contains no milk" | **Borderline real.** Inferred from the menu's vegan label; the reply did add that allergens are unconfirmed by the kitchen. |
| D3 | What should I try? | "The Falafel Plate is a popular choice" | **Probably judge error.** The knowledge text lists the plate at 90%. |
| C5 | Open on public holidays? | "Someone from the business can follow up" | **Judge artefact.** The offer to hand off is an action, not a factual claim. The hours answer itself ("not listed") is right. |
| R-C2 | Do you have wifi? | "Not mentioned in the business information", "someone can follow up" | **Judge artefact.** Same pattern: an honest "not listed" scored 0.0. |

Counting only the judge's output, faithfulness is 0.90. If the two artefacts and the probable judge error were set aside, it would be higher, but I am not reporting that as the result.

## Answer relevancy: why it is below 0.85

The three weakest groups explain most of the gap:

- **recommend 0.62.** "What is most popular?" and "I have $15" are answered with specific items; the generated questions drift to "what is on the menu" and score low.
- **info 0.74.** "Where are you located?" is answered correctly in one sentence (0.54). A correct short answer scores low because the metric infers questions from the answer.
- **Honest "not listed" replies** (wifi, public holidays) score 0.59 to 0.75 by construction.

So 0.80 reads as a metric limitation for short, direct replies more than as off-topic answers, but it is below the project's own gate and the deck should say so.

## Trajectory (11 golden tasks)

| Category | Cases | Passed |
|---|---|---|
| knowledge (hours, price, delivery, halal, unknown car park) | 5 | 5 |
| escalation (ask for a human, food-poisoning complaint) | 2 | 2 |
| quoting (item totals) | 4 | 0 |
| **Total** | **11** | **7 (0.64)** |

Knowledge and escalation behave as designed: right route, minimum steps, no invented figures, the complaint and the human request both escalate.

The four quoting failures, taken one by one:

- **Three (two plates and a lemonade; Super Plate and babyccinos; four chicken wraps).** The agent took the `structured` route and returned the engine's price summary ("Here is the current price summary."). The harness scores *formal rule-based quotes* (the tenant1 shape: a quote row, route `quoting`), so it marks these as wrong route and no quote row. This is a mismatch between my golden cases and how sababa2 prices item totals, not evidence that the totals are wrong. The totals themselves are graded in the main report (round 1 and 2 order-total cases, checked against catalog cents).
- **One real miss: "a large coffee and one hot chips, how much altogether?"** The agent took the `knowledge` route and quoted the two prices ($7.50 and $6.00) but gave no total. No money was invented, but the customer did not get the total they asked for.

I have not changed the harness or the cases to make these pass. The honest trajectory number is 7 of 11 with the explanation above; scoring the structured route properly needs a harness change (a `structured` row in its route table and an item-total check), which is a separate ticket.

## Events during the run

- The first Gemini key hit its daily quota after 6 replies (429). The Groq fallback then rejected the large judge prompt (413) and later its own daily token cap (200,000 tokens). The run stopped on 3 consecutive failures instead of retrying.
- A second key was put in the git-ignored `backend/.env` (old key kept as a commented spare). The next attempt hit a per-minute limit because each reply sends the whole corpus several times, so pacing went from 3 s to 20 s per reply and the run resumed, keeping the 5 replies already scored on the new key.
- Final run: 24 of 24 replies scored, 11 of 11 trajectory cases run, no errors in the stored results.

## Limits

- 24 replies and 11 cases is a small sample. The faithfulness figure has a wide margin; do not read 0.90 as a precise population value.
- The judge is the same model family as the agent. It makes mistakes in both directions (see the two artefacts above).
- Single run; no repeats were made to measure judge variance.
