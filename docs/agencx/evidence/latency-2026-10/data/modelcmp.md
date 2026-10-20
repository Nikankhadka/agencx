# DeepSeek vs Gemini vs Groq - real multi-turn comparison

Two back-to-back passes at HEAD `78685fc` (the config rows were uncommitted during the run), each one `make latency` invocation with all three models, `LATENCY_LEGS=single`, three turns in one reused conversation per tenant. Corpus tenants: `bytefix` (phone repair), `sababa2` (restaurant, fast path), `sababa` (restaurant, hybrid). n is small: 9 turn-slots per model per pass, 18 per model across both passes.

Command (identical for both passes):

```
make latency LATENCY_MODELS=openrouter/deepseek-v4-flash-latest,google/gemini-3.5-flash-lite,groq/openai-gpt-oss-120b LATENCY_TENANTS=all LATENCY_TURNS=3 LATENCY_CONVERSATION=reuse
```

## Probe and identity

The required probe (`POST /chat/completions`, `max_tokens: 8`) returned **HTTP 200** for the exact catalogue id `~deepseek/deepseek-v4-flash-latest`. No substitution was made. OpenRouter served the canonical `deepseek/deepseek-v4-flash-0731` via provider `Cohere`; every DeepSeek turn in both passes shows `usage_models: ["deepseek/deepseek-v4-flash-0731"]`. Because `model_match` is an exact comparison against the requested alias, it reads **false on all 18 DeepSeek turns even though the pinned alias answered every one**. The alias is the only difference; the canonical id is stable across all turns.

| model | catalogue id | pricing (prompt / completion / cache read, USD per token) |
|---|---|---|
| DeepSeek | `~deepseek/deepseek-v4-flash-latest` | `0.0000000114` / `0.00000045` / `0.0000000114` |
| Gemini | `models/gemini-3.5-flash-lite` | none published (`provider_pricing: null`) |
| Groq | `openai/gpt-oss-120b` | `0.00000015` / `0.0000006` / `0.000000075` |

The brief expected Groq pricing to be absent. The live Groq catalogue in this window **does** publish it, so the runner recorded it and the cost column is computed rather than `n/a`. That is a documented deviation from the expected input, not an invented figure.

## Completion rule

`done` = the turn emitted a `token` event, carried a route, and finished under 10,000 ms. `budget` = `total_ms >= 9,999` (the controller clamped the turn at the 10 s turn budget; no prose was delivered). `provider` = finished under 10 s with no `token` event (a provider fault was converted to a refusal/handoff before prose). `cum_ms` is the running sum of the three turns in that tenant; the third row is the 3-question cumulative. `leg` is null and `failover` false on every row because `LATENCY_LEGS` stayed `single`.

## Per-model summary

| model | pass | done/9 | budget | provider | p50 done, ms (n) | p50 all turns, ms (n) | cumulative per tenant, ms (bf / s2 / sa) | cache share | list cost | 429 / 413 / 503 |
|---|---|---|---|---|---|---|---|---|---|---|
| DeepSeek V4 Flash (OpenRouter) | 1 | 2/9 | 7 | 0 | 8069 (2) | 10008 (9) | 30029 / 28190 / 27991 | 3.4% (3328/98332) | $0.001325 | 0 / 0 / 0 |
| DeepSeek V4 Flash (OpenRouter) | 2 | 1/9 | 8 | 0 | 4992 (1) | 10006 (9) | 25006 / 30016 / 30021 | 53.1% (45824/86254) | $0.000939 | 0 / 0 / 0 |
| Gemini 3.5 Flash Lite (Google) | 1 | 4/9 | 2 | 3 | 3467 (4) | 3225 (9) | 2478 / 15257 / 23239 | 14.6% (20367/139390) | n/a | 4 / 0 / 2 |
| Gemini 3.5 Flash Lite (Google) | 2 | 7/9 | 1 | 1 | 4004 (7) | 4080 (9) | 11662 / 10613 / 25283 | 36.1% (41735/115641) | n/a | 9 / 0 / 0 |
| gpt-oss-120b (Groq) | 1 | 0/9 | 6 | 3 | n/a (0) | 10009 (9) | 30047 / 479 / 30029 | 0.0% (0/12414) | $0.002183 | 9 / 3 / 0 |
| gpt-oss-120b (Groq) | 2 | 0/9 | 6 | 3 | n/a (0) | 10009 (9) | 30030 / 360 / 30032 | 0.0% (0/10534) | $0.002393 | 12 / 3 / 0 |

Across both passes: DeepSeek **3/18** completed, Gemini **11/18**, Groq **0/18**. Per pass that is the requested out-of-9: DeepSeek 2/9 then 1/9; Gemini 4/9 then 7/9; Groq 0/9 then 0/9. The two passes share a window but not a Gemini quota state: run 1 opened with three immediate Gemini refusals on `bytefix` and closed with its best hybrid sample, while run 2 completed all three `bytefix` and `sababa2` turns.

## Ranking (completion first, then cumulative wait)

1. **Gemini 3.5 Flash Lite** - 11/18 done; completed fast-path turns were 2.8-4.3 s except one 8.8 s seven-call turn, and completed hybrid turns were 3.2-5.4 s; run 2's 3-question cumulatives were 11.7 s (bytefix), 10.6 s (sababa2), 25.3 s (sababa). Four turn-slots ended in provider refusals (429/503) and three more hit the budget, so its ceiling is quota-bound, not model-bound.
2. **DeepSeek V4 Flash** - 3/18 done; the three completions were 4,992 ms, 7,965 ms and 8,173 ms; every tenant cumulative was 25-30 s because 15/18 turns hit the 10 s budget. No provider errors in either pass.
3. **Groq gpt-oss-120b** - 0/18 done. Its 8,000 TPM free-tier ceiling rejects `sababa2` (the ~11k-token fast prompt) with HTTP 413 in ~100-190 ms before any call, and the other tenants burn the budget in 429 retries. Its 0.4 s `sababa2` cumulative is immediate failure, not a win.

Sample size: 18 turn-slots per model across two passes, 54 total. This is a small, single-window comparison; provider quota and queue state move more than the differences between adjacent ranks. The ordering of Gemini over DeepSeek is stable in both passes (Gemini completed more turns in each), but the exact ms values are not stable.

## DeepSeek V4 Flash (OpenRouter) - per turn

| run | tenant | turn | message | total_ms | result | calls | in_tok | cached | route / path | mm | leg / failover | cum_ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | bytefix | 1 | What repairs do you offer? | 10015.8 | budget | 1 | 5873 | 0 | knowledge / fast | false | none / false | 10015.8 |
| 1 | bytefix | 2 | How long do repairs usually take? | 10007.8 | budget | 1 | 5913 | 0 | knowledge / fast | false | none / false | 20023.6 |
| 1 | bytefix | 3 | Do you fix water-damaged phones? | 10005.5 | budget | 1 | 5955 | 0 | knowledge / fast | false | none / false | 30029.1 |
| 1 | sababa2 | 1 | Which dishes are vegan or gluten free? | 10006.3 | budget | 1 | 12185 | 0 | knowledge / fast | false | none / false | 10006.3 |
| 1 | sababa2 | 2 | What are your most popular items? | 10010.2 | budget | 1 | 12225 | 0 | knowledge / fast | false | none / false | 20016.5 |
| 1 | sababa2 | 3 | What time do you open? | 8173.1 | done | 2 | 20984 | 0 | knowledge / fast | false | none / false | 28189.6 |
| 1 | sababa | 1 | Which dishes are vegan or gluten free? | 10017.6 | budget | 2 | 16210 | 0 | recommendation / hybrid | false | none / false | 10017.6 |
| 1 | sababa | 2 | What are your most popular items? | 7965.3 | done | 3 | 15315 | 0 | knowledge / hybrid | false | none / false | 17982.9 |
| 1 | sababa | 3 | What time do you open? | 10007.8 | budget | 1 | 3672 | 3328 | conversation / hybrid | false | none / false | 27990.7 |
| 2 | bytefix | 1 | What repairs do you offer? | 10007.8 | budget | 1 | 5873 | 0 | knowledge / fast | false | none / false | 10007.8 |
| 2 | bytefix | 2 | How long do repairs usually take? | 4992.0 | done | 2 | 8693 | 5632 | knowledge / fast | false | none / false | 14999.8 |
| 2 | bytefix | 3 | Do you fix water-damaged phones? | 10006.4 | budget | 1 | 5991 | 5632 | knowledge / fast | false | none / false | 25006.2 |
| 2 | sababa2 | 1 | Which dishes are vegan or gluten free? | 10005.5 | budget | 1 | 12185 | 11776 | knowledge / fast | false | none / false | 10005.5 |
| 2 | sababa2 | 2 | What are your most popular items? | 10005.0 | budget | 1 | 12225 | 0 | knowledge / fast | false | none / false | 20010.5 |
| 2 | sababa2 | 3 | What time do you open? | 10005.5 | budget | 1 | 12264 | 11776 | knowledge / fast | false | none / false | 30016.0 |
| 2 | sababa | 1 | Which dishes are vegan or gluten free? | 10006.4 | budget | 2 | 12057 | 0 | recommendation / hybrid | false | none / false | 10006.4 |
| 2 | sababa | 2 | What are your most popular items? | 10006.7 | budget | 2 | 11397 | 6656 | knowledge / hybrid | false | none / false | 20013.1 |
| 2 | sababa | 3 | What time do you open? | 10007.6 | budget | 3 | 5569 | 4352 | conversation / hybrid | false | none / false | 30020.7 |

## Gemini 3.5 Flash Lite (Google) - per turn

| run | tenant | turn | message | total_ms | result | calls | in_tok | cached | route / path | mm | leg / failover | cum_ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | bytefix | 1 | What repairs do you offer? | 1035.2 | provider | 0 | 0 | 0 | - / fast | false | none / false | 1035.2 |
| 1 | bytefix | 2 | How long do repairs usually take? | 815.3 | provider | 0 | 0 | 0 | - / fast | false | none / false | 1850.5 |
| 1 | bytefix | 3 | Do you fix water-damaged phones? | 627.0 | provider | 0 | 0 | 0 | - / fast | false | none / false | 2477.5 |
| 1 | sababa2 | 1 | Which dishes are vegan or gluten free? | 3709.8 | done | 2 | 22493 | 0 | knowledge / fast | true | none / false | 3709.8 |
| 1 | sababa2 | 2 | What are your most popular items? | 8795.6 | done | 7 | 76640 | 10186 | knowledge / fast | true | none / false | 12505.4 |
| 1 | sababa2 | 3 | What time do you open? | 2751.3 | done | 2 | 22676 | 10181 | knowledge / fast | true | none / false | 15256.7 |
| 1 | sababa | 1 | Which dishes are vegan or gluten free? | 10006.6 | budget | 2 | 10637 | 0 | knowledge / hybrid | true | none / false | 10006.6 |
| 1 | sababa | 2 | What are your most popular items? | 10007.7 | budget | 1 | 3194 | 0 | - / hybrid | true | none / false | 20014.3 |
| 1 | sababa | 3 | What time do you open? | 3224.9 | done | 2 | 3750 | 0 | conversation / hybrid | true | none / false | 23239.2 |
| 2 | bytefix | 1 | What repairs do you offer? | 4080.1 | done | 2 | 8701 | 0 | knowledge / fast | true | none / false | 4080.1 |
| 2 | bytefix | 2 | How long do repairs usually take? | 4289.1 | done | 2 | 8869 | 2024 | knowledge / fast | true | none / false | 8369.2 |
| 2 | bytefix | 3 | Do you fix water-damaged phones? | 3293.3 | done | 2 | 8930 | 2022 | knowledge / fast | true | none / false | 11662.5 |
| 2 | sababa2 | 1 | Which dishes are vegan or gluten free? | 3198.4 | done | 2 | 22486 | 7543 | knowledge / fast | true | none / false | 3198.4 |
| 2 | sababa2 | 2 | What are your most popular items? | 4003.6 | done | 2 | 22656 | 10186 | knowledge / fast | true | none / false | 7202.0 |
| 2 | sababa2 | 3 | What time do you open? | 3411.4 | done | 2 | 22720 | 17719 | knowledge / fast | true | none / false | 10613.4 |
| 2 | sababa | 1 | Which dishes are vegan or gluten free? | 5445.5 | done | 3 | 14575 | 2241 | knowledge / hybrid | true | none / false | 5445.5 |
| 2 | sababa | 2 | What are your most popular items? | 9829.5 | provider | 1 | 3372 | 0 | - / hybrid | true | none / false | 15275.0 |
| 2 | sababa | 3 | What time do you open? | 10008.1 | budget | 1 | 3332 | 0 | conversation / hybrid | true | none / false | 25283.1 |

## gpt-oss-120b (Groq) - per turn

| run | tenant | turn | message | total_ms | result | calls | in_tok | cached | route / path | mm | leg / failover | cum_ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | bytefix | 1 | What repairs do you offer? | 10012.8 | budget | 1 | 4861 | 0 | knowledge / fast | true | none / false | 10012.8 |
| 1 | bytefix | 2 | How long do repairs usually take? | 10020.1 | budget | 0 | 0 | 0 | - / fast | false | none / false | 20032.9 |
| 1 | bytefix | 3 | Do you fix water-damaged phones? | 10014.4 | budget | 1 | 4950 | 0 | knowledge / fast | true | none / false | 30047.3 |
| 1 | sababa2 | 1 | Which dishes are vegan or gluten free? | 152.8 | provider | 0 | 0 | 0 | - / fast | false | none / false | 152.8 |
| 1 | sababa2 | 2 | What are your most popular items? | 188.2 | provider | 0 | 0 | 0 | - / fast | false | none / false | 341.0 |
| 1 | sababa2 | 3 | What time do you open? | 137.8 | provider | 0 | 0 | 0 | - / fast | false | none / false | 478.8 |
| 1 | sababa | 1 | Which dishes are vegan or gluten free? | 10006.7 | budget | 0 | 0 | 0 | - / hybrid | false | none / false | 10006.7 |
| 1 | sababa | 2 | What are your most popular items? | 10013.3 | budget | 0 | 0 | 0 | - / hybrid | false | none / false | 20020.0 |
| 1 | sababa | 3 | What time do you open? | 10009.3 | budget | 1 | 2603 | 0 | conversation / hybrid | true | none / false | 30029.3 |
| 2 | bytefix | 1 | What repairs do you offer? | 10006.6 | budget | 2 | 7931 | 0 | knowledge / fast | true | none / false | 10006.6 |
| 2 | bytefix | 2 | How long do repairs usually take? | 10008.9 | budget | 0 | 0 | 0 | - / fast | false | none / false | 20015.5 |
| 2 | bytefix | 3 | Do you fix water-damaged phones? | 10014.2 | budget | 0 | 0 | 0 | - / fast | false | none / false | 30029.7 |
| 2 | sababa2 | 1 | Which dishes are vegan or gluten free? | 103.9 | provider | 0 | 0 | 0 | - / fast | false | none / false | 103.9 |
| 2 | sababa2 | 2 | What are your most popular items? | 144.9 | provider | 0 | 0 | 0 | - / fast | false | none / false | 248.8 |
| 2 | sababa2 | 3 | What time do you open? | 110.9 | provider | 0 | 0 | 0 | - / fast | false | none / false | 359.7 |
| 2 | sababa | 1 | Which dishes are vegan or gluten free? | 10012.3 | budget | 0 | 0 | 0 | - / hybrid | false | none / false | 10012.3 |
| 2 | sababa | 2 | What are your most popular items? | 10009.8 | budget | 0 | 0 | 0 | - / hybrid | false | none / false | 20022.1 |
| 2 | sababa | 3 | What time do you open? | 10009.7 | budget | 1 | 2603 | 0 | conversation / hybrid | true | none / false | 30031.8 |

## Error detail

- **Gemini**: run 1 logged 4 x 429 and 2 x 503; three `bytefix` turns were refused in about 0.6-1.0 s with zero calls (capacity/quota, before route). Run 2 logged 9 x 429, two of them `RESOURCE_EXHAUSTED` free-tier quota; one hybrid turn failed mid-stream at 9,829 ms and one hit the budget. No retry exceeded the one bounded retry path already in the provider; the runner never retries a turn itself.
- **Groq**: every `sababa2` request was rejected with HTTP 413, "Request too large ... tokens per minute (TPM): Limit 8000, Requested 11,076-11,233". `bytefix` and `sababa` show 429 retry storms (9 and 12 occurrences per pass) and 6 budget turns per pass. 0 completions.
- **DeepSeek**: no 429, 413 or 5xx in either pass. All 18 turns reached the model; 15 were clamped by the 10 s turn budget. The slowness is the model/provider, not a rate limit.

## Cache economics

DeepSeek run 1 cache share was 3.4% (3,328/98,332 input tokens); run 2 was 53.1% (45,824/86,254), because run 1 had already warmed the tenant prefixes. Gemini went 14.6% then 36.1%. Groq read no cache. DeepSeek's published cache-read price is identical to its prompt price (`0.0000000114`), so caching there reduces latency (fewer prompt tokens to process) but **saves no money**. This is the opposite of the usual cache discount and is why the DeepSeek cost line does not fall with the higher run-2 hit rate.
