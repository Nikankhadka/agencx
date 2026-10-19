# Slice 6 addendum - production primary (Google gemini-3.5-flash-lite)

**Provider probe.** `https://generativelanguage.googleapis.com/v1beta/openai/models` returns the OpenAI-list shape (`{"object", "data": [{"id", "object", "owned_by", "display_name"}]}`, 63 entries), so `_fetch_provider_models` / `_find_model` work unchanged. The catalogue id is **`models/gemini-3.5-flash-lite`** (with the `models/` prefix); the chat endpoint accepts both the bare and prefixed forms and echoes the requested form, so the config carries the catalogue id. **No pricing fields are published** - `provider_pricing` is `null` in every artifact, so cost is `n/a` and no price is invented.

**Command (identical for both runs):**

```
make latency LATENCY_MODELS=google/gemini-3.5-flash-lite LATENCY_TENANTS=all LATENCY_TURNS=5
```

At `8ebf463` + the config row. The runner pins `LLM_MODEL`, empties fallback/failover, and `model_match` is true on every reporting turn. Cost column: Google publishes no prices, so `_summary` leaves it `None`.

## Run 1

Artifacts 15:48:11-15:49:34Z (2026-10-19).

| tenant | path | route(s) completed | turns (completed/total) | p50 total_ms | p95 total_ms | calls (all turns) | in/out tok | cache tok | model_match | failover | cost |
|---|---|---|---|---|---|---|---|---|---|---|---|
| bytefix | fast | knowledge | 3/5 | 8355.2 | 8750.5 | [1, 2] | 37511/622 | 8104 | True | False | n/a |
| sababa2 | fast | knowledge | 3/5 | 6248.8 | 6812.4 | [1, 2] | 92962/747 | 40768 | True | False | n/a |
| sababa | hybrid | conversation,knowledge | 4/5 | 5897.6 | 8875.6 | [1, 2, 3] | 50446/912 | 0 | True | False | n/a |

## Run 2

Artifacts 15:51:06-15:52:39Z, turns through 15:53:30Z (2026-10-19).

| tenant | path | route(s) completed | turns (completed/total) | p50 total_ms | p95 total_ms | calls (all turns) | in/out tok | cache tok | model_match | failover | cost |
|---|---|---|---|---|---|---|---|---|---|---|---|
| bytefix | fast | knowledge | 1/5 | 8581.9 | 8581.9 | [1, 2] | 31686/354 | 10130 | True | False | n/a |
| sababa2 | fast | knowledge | 1/5 | 3625.8 | 3625.8 | [1, 2] | 73718/447 | 58497 | True | False | n/a |
| sababa | hybrid | - | 0/5 | - | - | [0] | 0/0 | 0 | False | False | n/a |

## Run 1 vs run 2

| tenant | completed r1 / r2 | p50 total_ms r1 / r2 | calls r1 / r2 | cache tok r1 / r2 |
|---|---|---|---|---|
| bytefix | 3/5 / 1/5 | 8355.2 / 8581.9 | [1, 2] / [1, 2] | 8104 / 10130 |
| sababa2 | 3/5 / 1/5 | 6248.8 / 3625.8 | [1, 2] / [1, 2] | 40768 / 58497 |
| sababa | 4/5 / 0/5 | 5897.6 / - | [1, 2, 3] / [0] | 0 / 0 |

## Notes

- Completion is window-dependent, not stable: run 1 completed 10/15 turns, run 2 completed 2/15. Run 2's `sababa` turns logged Google 429s (`llm rate-limited; retrying`) and hit the 10 s budget before any call completed (`llm_call_count` 0, `route` null), so that row is censored rather than answered.
- Run 1's completed `sababa` turns are drafted-answer routes (`knowledge`, `conversation`), not card turns; all completed rows are `fast` on bytefix/sababa2 and `hybrid` on sababa. The single run-1 `sababa` turn 5 ended in a mid-stream handoff after two 429 retries.
- Run 2's `sababa` row shows `model_match` False because none of its turns reached the model (`usage_models` empty), not because a different model answered; the other reporting rows are True on every completed turn.
- No cost: Google's models endpoint publishes no pricing. The token counts are reported so a price can be applied later if one is obtained.
- Percentiles are over completed turns only; `calls (all turns)` is the set over every turn, so a censored turn's calls still show.

## Provenance

- run 1 - bytefix: `make latency LATENCY_MODELS=google/gemini-3.5-flash-lite LATENCY_TENANTS=all LATENCY_TURNS=5` at 2026-10-19T15:48:11Z
- run 1 - sababa2: `make latency LATENCY_MODELS=google/gemini-3.5-flash-lite LATENCY_TENANTS=all LATENCY_TURNS=5` at 2026-10-19T15:48:56Z
- run 1 - sababa: `make latency LATENCY_MODELS=google/gemini-3.5-flash-lite LATENCY_TENANTS=all LATENCY_TURNS=5` at 2026-10-19T15:49:34Z
- run 2 - bytefix: `make latency LATENCY_MODELS=google/gemini-3.5-flash-lite LATENCY_TENANTS=all LATENCY_TURNS=5` at 2026-10-19T15:51:06Z
- run 2 - sababa2: `make latency LATENCY_MODELS=google/gemini-3.5-flash-lite LATENCY_TENANTS=all LATENCY_TURNS=5` at 2026-10-19T15:51:55Z
- run 2 - sababa: `make latency LATENCY_MODELS=google/gemini-3.5-flash-lite LATENCY_TENANTS=all LATENCY_TURNS=5` at 2026-10-19T15:52:39Z
Raw stdout: `data/slice6-google-run1.log`, `data/slice6-google-run2.log`.
