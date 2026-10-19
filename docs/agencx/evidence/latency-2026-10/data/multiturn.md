# Multi-turn measurement - reused conversations

Measured at `3fb604a` on `latency/stack`. Two back-to-back runs of the same
command, deepseek pinned, all three tenants, five turns each, one conversation
per tenant per run:

```
make latency LATENCY_CONVERSATION=reuse LATENCY_MODELS=openrouter/deepseek-v4.1-flash LATENCY_TENANTS=all LATENCY_TURNS=5
```

Before this commit the runner passed `conversation_id=None` on every turn, so
every prior artifact is single-turn no matter what `--turns` said. The artifact
now carries `"conversation_mode": "reuse"`, and the runner passes the id from
turn 1 into turns 2-5. Reuse is verified in the database: each of the six
conversations holds exactly 10 messages, alternating `customer,assistant`, so
each later turn really ran against the growing transcript.

Raw data: `multiturn-run{1,2}.log` (runner stdout) and
`multiturn-run{1,2}-openrouter-deepseek-v4-1-flash__<tenant>.json` (per-tenant
artifacts). `completed` means customer prose reached the customer
(`first_prose_ms` non-null); `budget` means the 10 s turn budget fired and the
turn handed off (`total_ms` pinned at ~10,000, `first_prose_ms` null).

## Case counts (first)

| Run | Turns attempted | Latency records | Error turns | Completed | Budget handoffs |
|---|---|---|---|---|---|
| 1 | 15 | 15 | 0 | 4 | 11 |
| 2 | 15 | 15 | 0 | 0 | 15 |
| **Total** | **30** | **30** | **0** | **4** | **26** |

Run 1 completed: bytefix 2/5, sababa2 1/5, sababa 1/5. Run 2 completed: 0/5 on
every tenant. `model_match` is true on all 30 turns, no failover, no rate-limit
retries.

## Per turn

`cum total_ms` is the running sum across the five turns of that conversation.
Status is completed or budget.

| Run | Tenant | Turn | Message | total_ms | Path | Route | Calls | Status | Input tok | Cached tok | cum total_ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | bytefix | 1 | What repairs do you offer? | 3232.9 | fast | structured | 1 | completed | 5810 | 0 | 3232.9 |
| 1 | bytefix | 2 | How long do repairs usually take? | 7462.8 | fast | knowledge | 2 | completed | 8683 | 4352 | 10695.7 |
| 1 | bytefix | 3 | Do you fix water-damaged phones? | 10007.9 | fast | knowledge | 1 | budget | 6027 | 5888 | 20703.6 |
| 1 | bytefix | 4 | Do you offer a warranty on your repairs? | 10006.1 | fast | knowledge | 1 | budget | 5978 | 5760 | 30709.7 |
| 1 | bytefix | 5 | Can you replace a charging port? | 10007.3 | fast | knowledge | 1 | budget | 6018 | 5888 | 40717.0 |
| 1 | sababa2 | 1 | Which dishes are vegan or gluten free? | 7587.1 | fast | knowledge | 2 | completed | 20987 | 0 | 7587.1 |
| 1 | sababa2 | 2 | What are your most popular items? | 10006.3 | fast | knowledge | 1 | budget | 12481 | 10752 | 17593.4 |
| 1 | sababa2 | 3 | What time do you open? | 10005.5 | fast | knowledge | 1 | budget | 12429 | 12032 | 27598.9 |
| 1 | sababa2 | 4 | Do you have anything without nuts? | 10006.8 | fast | knowledge | 1 | budget | 12469 | 12416 | 37605.7 |
| 1 | sababa2 | 5 | What is the Super Plate? | 10006.0 | fast | knowledge | 1 | budget | 12508 | 12416 | 47611.7 |
| 1 | sababa | 1 | Which dishes are vegan or gluten free? | 10008.3 | hybrid | - | 1 | budget | 3469 | 0 | 10008.3 |
| 1 | sababa | 2 | What are your most popular items? | 10005.1 | hybrid | knowledge | 2 | budget | 11250 | 3328 | 20013.4 |
| 1 | sababa | 3 | What time do you open? | 9716.7 | hybrid | knowledge | 3 | completed | 15561 | 6656 | 29730.1 |
| 1 | sababa | 4 | Do you have anything without nuts? | 10005.0 | hybrid | recommendation | 2 | budget | 12014 | 3328 | 39735.1 |
| 1 | sababa | 5 | What is the Super Plate? | 10004.6 | hybrid | recommendation | 2 | budget | 8200 | 6912 | 49739.7 |
| 2 | bytefix | 1 | What repairs do you offer? | 10011.7 | fast | knowledge | 1 | budget | 5810 | 5760 | 10011.7 |
| 2 | bytefix | 2 | How long do repairs usually take? | 10007.0 | fast | knowledge | 1 | budget | 5850 | 5760 | 20018.7 |
| 2 | bytefix | 3 | Do you fix water-damaged phones? | 10007.1 | fast | knowledge | 1 | budget | 5892 | 5760 | 30025.8 |
| 2 | bytefix | 4 | Do you offer a warranty on your repairs? | 10009.4 | fast | knowledge | 1 | budget | 5934 | 5888 | 40035.2 |
| 2 | bytefix | 5 | Can you replace a charging port? | 10005.4 | fast | knowledge | 1 | budget | 5974 | 5888 | 50040.6 |
| 2 | sababa2 | 1 | Which dishes are vegan or gluten free? | 10006.5 | fast | knowledge | 1 | budget | 12124 | 12032 | 10006.5 |
| 2 | sababa2 | 2 | What are your most popular items? | 10005.9 | fast | knowledge | 1 | budget | 12164 | 12032 | 20012.4 |
| 2 | sababa2 | 3 | What time do you open? | 10006.6 | fast | knowledge | 1 | budget | 12203 | 12160 | 30019.0 |
| 2 | sababa2 | 4 | Do you have anything without nuts? | 10008.4 | fast | knowledge | 1 | budget | 12243 | 12160 | 40027.4 |
| 2 | sababa2 | 5 | What is the Super Plate? | 10008.7 | fast | knowledge | 1 | budget | 12282 | 12160 | 50036.1 |
| 2 | sababa | 1 | Which dishes are vegan or gluten free? | 10006.3 | hybrid | recommendation | 2 | budget | 11778 | 3328 | 10006.3 |
| 2 | sababa | 2 | What are your most popular items? | 10006.3 | hybrid | knowledge | 3 | budget | 16441 | 6656 | 20012.6 |
| 2 | sababa | 3 | What time do you open? | 10006.3 | hybrid | conversation | 1 | budget | 3548 | 3328 | 30018.9 |
| 2 | sababa | 4 | Do you have anything without nuts? | 10005.6 | hybrid | recommendation | 2 | budget | 12108 | 3328 | 40024.5 |
| 2 | sababa | 5 | What is the Super Plate? | 10007.1 | hybrid | recommendation | 2 | budget | 8163 | 6656 | 50031.6 |

## Per tenant and run

`cum 1/2/3` is the cumulative wall time after the first one, two and three
questions. Cache share is `cached_input_tokens / input_tokens` per turn. Input
growth is turn 1 to turn 5.

| Run | Tenant | Completed | cum 1 | cum 2 | cum 3 | cum 5 | Cache share by turn | Input t1 -> t5 |
|---|---|---|---|---|---|---|---|---|
| 1 | bytefix | 2/5 | 3232.9 | 10695.7 | 20703.6 | 40717.0 | 0.0, 50.1, 97.7, 96.4, 97.8% | 5810 -> 6018 (+208) |
| 1 | sababa2 | 1/5 | 7587.1 | 17593.4 | 27598.9 | 47611.7 | 0.0, 86.1, 96.8, 99.6, 99.3% | 20987 -> 12508 (-8479) |
| 1 | sababa | 1/5 | 10008.3 | 20013.4 | 29730.1 | 49739.7 | 0.0, 29.6, 42.8, 27.7, 84.3% | 3469 -> 8200 (+4731) |
| 2 | bytefix | 0/5 | 10011.7 | 20018.7 | 30025.8 | 50040.6 | 99.1, 98.5, 97.8, 99.2, 98.6% | 5810 -> 5974 (+164) |
| 2 | sababa2 | 0/5 | 10006.5 | 20012.4 | 30019.0 | 50036.1 | 99.2, 98.9, 99.6, 99.3, 99.0% | 12124 -> 12282 (+158) |
| 2 | sababa | 0/5 | 10006.3 | 20012.6 | 30018.9 | 50031.6 | 28.3, 40.5, 93.8, 27.5, 81.5% | 11778 -> 8163 (-3615) |

## What the data says

**Case counts first.** 30 turns attempted, 30 latency records, 0 errors, only
4 completed, 26 handoffs at the 10 s budget (run 1: 11/15, run 2: 15/15).

**Later turns do not show a slowdown, and the instrument cannot show one.**
Twenty-six of thirty turns are clamped at ~10,000 ms by the budget, so their
`total_ms` is a ceiling, not a duration. The four completed turns are different
route classes (a 3.2 s structured card, two knowledge turns at 7.5-7.5 s, one
hybrid knowledge turn at 9.7 s), so they do not form a turn-order trend. The
cumulative columns mostly measure 10 s x N because almost every turn hit the
wall.

**Cache share rises with history in a cold conversation, then saturates.** Run
1 starts cold on every tenant's turn 1 (0% cached) and rises to 84-99% by turn
5 for the fast tenants. Run 2 starts warm because run 1 left the prompt prefixes
in the provider cache: fast tenants sit at 97.8-99.6% throughout. Hybrid sababa
is lower and non-monotone (27.5-93.8%) because each turn's tool results and
route-specific sections are new tokens. This is prefix caching across requests,
not conversation-scoped state: run 2's turn 1 is cached although it is a new
conversation.

**History growth is small, and the 10-message cap never binds at five turns.**
For a fixed one-call shape the transcript adds about 40 input tokens per turn
(bytefix run 2: 5810 -> 5974 over four intervals; sababa2 run 2: 12124 ->
12282). The turn-1 to turn-5 deltas in the table are dominated by call count
and route, not history: sababa2 run 1 falls because turn 1 made two calls and
carried 21.0k tokens. At turn 5 the history read sees 9 rows against the
`HISTORY_MESSAGES = 10` cap, so the cap is not what shapes this window.

**Handoffs, not answers, are the dominant outcome.** 26/30 turns produced a
refusal plus handoff at 10 s. That is the multi-turn fact any lever has to move.
