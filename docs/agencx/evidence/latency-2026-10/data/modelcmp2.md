# Four-model comparison - DeepSeek, Gemini, Groq, gpt-oss-20b

Two back-to-back passes at HEAD `9ea418c` (2026-10-20), each one `make latency` invocation with all four models, `LATENCY_LEGS=single`, three turns in one reused conversation per tenant. Corpus: `bytefix` (phone repair), `sababa2` (restaurant, fast path), `sababa` (restaurant, hybrid). n is small: 9 turn-slots per model per pass, 18 per model across both passes.

Command (identical for both passes):

```
make latency LATENCY_MODELS=openrouter/deepseek-v4-flash-latest,google/gemini-3.5-flash-lite,groq/openai-gpt-oss-120b,openrouter/openai-gpt-oss-20b LATENCY_TENANTS=all LATENCY_TURNS=3 LATENCY_CONVERSATION=reuse
```

The runner selects config rows in config order, not command order, so the measured order was Gemini, DeepSeek, Groq, gpt-oss-20b. All four ran single-leg.

## Probe and identity

The probe (`POST /chat/completions`, no reasoning-effort override) returned **HTTP 200** for the exact catalogue id `openai/gpt-oss-20b` (no tilde). OpenRouter served `openai/gpt-oss-20b` via three different upstream providers across the three probe calls: **DeepInfra** (plain chat), **Darkbloom** (tools), **AkashML** (structured outputs). Tools worked: the model returned a valid `get_weather` call with `{"city":"Kathmandu"}`. Structured outputs worked: `response_format: json_schema` returned `{"ok": true}` and parsed. Plain chat with `max_tokens: 16` returned no prose at all because 13 reasoning tokens consumed the cap (`finish_reason: length`). The probe recorded 13-35 reasoning tokens per call, which is the latency warning: the app sets no reasoning-effort override, so every turn pays the hidden thinking.

| model | catalogue id | pricing (prompt / completion / cache read, USD per token) |
|---|---|---|
| DeepSeek | `~deepseek/deepseek-v4-flash-latest` | `0.0000000049` / `0.00000045` / `0.0000000049` |
| Gemini | `models/gemini-3.5-flash-lite` | none published (`provider_pricing: null`) |
| Groq | `openai/gpt-oss-120b` | `0.00000015` / `0.0000006` / `0.000000075` |
| gpt-oss-20b | `openai/gpt-oss-20b` | `0.000000018` / `0.00000009` / `0.000000009` |

DeepSeek's prompt price moved between windows: `0.0000000114` in the prior `modelcmp.md` window, `0.0000000049` here. Completion (`0.00000045`) did not move, and cache read still equals prompt. Costs below are computed from each window's own artifact and are never pooled.

## Completion rule

`done` = the turn emitted a `token` event, carried a route, and finished under 10,000 ms. `budget` = `total_ms >= 9,999` (the controller clamped the turn at the 10 s turn budget; no prose was delivered). `provider` = finished under 10 s with no `token` event (a provider fault was converted to a refusal/handoff before prose). `cum_ms` is the running sum of the three turns in that tenant; the third row is the 3-question cumulative. `leg` is null and `failover` false on every row because `LATENCY_LEGS` stayed `single`.

## Per-model summary

| model | pass | done/9 | budget | provider | p50 done, ms (n) | p50 all turns, ms (n) | cumulative per tenant, ms (bf / s2 / sa) | cache share | list cost | 429 / 413 / 5xx |
|---|---|---|---|---|---|---|---|---|---|---|
| DeepSeek V4 Flash (OpenRouter) | 1 | 3/9 | 6 | 0 | 4979 (3) | 10007 (9) | 27816 / 19598 / 30024 | 27.8% (29696/106778) | $0.002446 | 0 / 0 / 0 |
| DeepSeek V4 Flash (OpenRouter) | 2 | 2/9 | 7 | 0 | 8017 (2) | 10007 (9) | 29773 / 26288 / 30023 | 7.6% (5888/76988) | $0.000681 | 0 / 0 / 0 |
| Gemini 3.5 Flash Lite (Google) | 1 | 7/9 | 0 | 2 | 4245 (7) | 7165 (9) | 18015 / 10736 / 22245 | 18.5% (24413/131956) | n/a | 7 / 0 / 0 |
| Gemini 3.5 Flash Lite (Google) | 2 | 7/9 | 1 | 1 | 3787 (7) | 3988 (9) | 12138 / 9737 / 28351 | 20.0% (22389/111932) | n/a | 7 / 0 / 0 |
| gpt-oss-120b (Groq) | 1 | 0/9 | 6 | 3 | n/a (0) | 10006 (9) | 30025 / 464 / 30027 | 0.0% (0/11467) | $0.002583 | 11 / 3 / 0 |
| gpt-oss-120b (Groq) | 2 | 0/9 | 6 | 3 | n/a (0) | 10008 (9) | 30027 / 446 / 30035 | 0.0% (0/11433) | $0.002752 | 10 / 3 / 0 |
| gpt-oss-20b (OpenRouter) | 1 | 0/9 | 9 | 0 | n/a (0) | 10006 (9) | 30016 / 30027 / 30018 | 0.0% (0/12447) | $0.000263 | 0 / 0 / 0 |
| gpt-oss-20b (OpenRouter) | 2 | 0/9 | 9 | 0 | n/a (0) | 10007 (9) | 30020 / 30018 / 30025 | 23.2% (4096/17656) | $0.000318 | 0 / 0 / 0 |

Across both passes: Gemini **14/18**, DeepSeek **5/18**, Groq **0/18**, gpt-oss-20b **0/18**. Per pass that is Gemini 7/9 then 7/9; DeepSeek 3/9 then 2/9; Groq 0/9 then 0/9; gpt-oss-20b 0/9 then 0/9. This window is sunnier for Gemini than the prior `modelcmp.md` window (11/18 there: 4/9 then 7/9), and the DeepSeek prompt price is less than half the prior window's, so do not read these pass costs as comparable to the prior table without that label.

## Per-turn

### DeepSeek V4 Flash (OpenRouter)

| run | tenant | turn | message | total_ms | result | calls | in_tok | cached | route / path | mm | leg / failover | cum_ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | bytefix | 1 | What repairs do you offer? | 10009.2 | budget | 1 | 5873 | 0 | knowledge / fast | false | none / false | 10009.2 |
| 1 | bytefix | 2 | How long do repairs usually take? | 10004.8 | budget | 1 | 5913 | 5632 | knowledge / fast | false | none / false | 20014.0 |
| 1 | bytefix | 3 | Do you fix water-damaged phones? | 7802.4 | done | 2 | 8752 | 5632 | knowledge / fast | false | none / false | 27816.4 |
| 1 | sababa2 | 1 | Which dishes are vegan or gluten free? | 10007.4 | budget | 1 | 12185 | 0 | knowledge / fast | false | none / false | 10007.4 |
| 1 | sababa2 | 2 | What are your most popular items? | 4979.2 | done | 2 | 21381 | 11776 | knowledge / fast | false | none / false | 14986.6 |
| 1 | sababa2 | 3 | What time do you open? | 4611.9 | done | 2 | 21424 | 0 | knowledge / fast | false | none / false | 19598.5 |
| 1 | sababa | 1 | Which dishes are vegan or gluten free? | 10009.4 | budget | 2 | 16283 | 0 | recommendation / hybrid | false | none / false | 10009.4 |
| 1 | sababa | 2 | What are your most popular items? | 10006.8 | budget | 2 | 11356 | 3328 | knowledge / hybrid | false | none / false | 20016.2 |
| 1 | sababa | 3 | What time do you open? | 10008.1 | budget | 1 | 3611 | 3328 | conversation / hybrid | false | none / false | 30024.3 |
| 2 | bytefix | 1 | What repairs do you offer? | 10007.3 | budget | 1 | 5873 | 0 | knowledge / fast | false | none / false | 10007.3 |
| 2 | bytefix | 2 | How long do repairs usually take? | 10006.1 | budget | 1 | 5913 | 0 | knowledge / fast | false | none / false | 20013.4 |
| 2 | bytefix | 3 | Do you fix water-damaged phones? | 9759.3 | done | 2 | 9114 | 5888 | knowledge / fast | false | none / false | 29772.7 |
| 2 | sababa2 | 1 | Which dishes are vegan or gluten free? | 10006.1 | budget | 1 | 12185 | 0 | knowledge / fast | false | none / false | 10006.1 |
| 2 | sababa2 | 2 | What are your most popular items? | 10007.4 | budget | 1 | 12225 | 0 | knowledge / fast | false | none / false | 20013.5 |
| 2 | sababa2 | 3 | What time do you open? | 6275.0 | done | 2 | 20963 | 0 | knowledge / fast | false | none / false | 26288.5 |
| 2 | sababa | 1 | Which dishes are vegan or gluten free? | 10006.9 | budget | 1 | 3532 | 0 | - / hybrid | false | none / false | 10006.9 |
| 2 | sababa | 2 | What are your most popular items? | 10008.2 | budget | 1 | 3572 | 0 | - / hybrid | false | none / false | 20015.1 |
| 2 | sababa | 3 | What time do you open? | 10007.8 | budget | 1 | 3611 | 0 | conversation / hybrid | false | none / false | 30022.9 |

### Gemini 3.5 Flash Lite (Google)

| run | tenant | turn | message | total_ms | result | calls | in_tok | cached | route / path | mm | leg / failover | cum_ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | bytefix | 1 | What repairs do you offer? | 7636.8 | done | 2 | 8672 | 0 | knowledge / fast | true | none / false | 7636.8 |
| 1 | bytefix | 2 | How long do repairs usually take? | 7164.6 | done | 8 | 31961 | 2024 | knowledge / fast | true | none / false | 14801.4 |
| 1 | bytefix | 3 | Do you fix water-damaged phones? | 3213.9 | done | 2 | 8888 | 2022 | knowledge / fast | true | none / false | 18015.3 |
| 1 | sababa2 | 1 | Which dishes are vegan or gluten free? | 4244.9 | done | 2 | 22489 | 0 | knowledge / fast | true | none / false | 4244.9 |
| 1 | sababa2 | 2 | What are your most popular items? | 3485.4 | done | 2 | 22663 | 10186 | knowledge / fast | true | none / false | 7730.3 |
| 1 | sababa2 | 3 | What time do you open? | 3005.4 | done | 2 | 22708 | 10181 | knowledge / fast | true | none / false | 10735.7 |
| 1 | sababa | 1 | Which dishes are vegan or gluten free? | 7205.6 | done | 3 | 14575 | 0 | knowledge / hybrid | true | none / false | 7205.6 |
| 1 | sababa | 2 | What are your most popular items? | 7580.1 | provider | 0 | 0 | 0 | - / hybrid | false | none / false | 14785.7 |
| 1 | sababa | 3 | What time do you open? | 7459.4 | provider | 0 | 0 | 0 | - / hybrid | false | none / false | 22245.1 |
| 2 | bytefix | 1 | What repairs do you offer? | 3988.4 | done | 2 | 8711 | 0 | knowledge / fast | true | none / false | 3988.4 |
| 2 | bytefix | 2 | How long do repairs usually take? | 3786.6 | done | 2 | 8871 | 0 | knowledge / fast | true | none / false | 7775.0 |
| 2 | bytefix | 3 | Do you fix water-damaged phones? | 4362.8 | done | 2 | 8929 | 2022 | knowledge / fast | true | none / false | 12137.8 |
| 2 | sababa2 | 1 | Which dishes are vegan or gluten free? | 3155.1 | done | 2 | 22486 | 0 | knowledge / fast | true | none / false | 3155.1 |
| 2 | sababa2 | 2 | What are your most popular items? | 3079.8 | done | 2 | 22655 | 10186 | knowledge / fast | true | none / false | 6234.9 |
| 2 | sababa2 | 3 | What time do you open? | 3502.2 | done | 2 | 22695 | 10181 | knowledge / fast | true | none / false | 9737.1 |
| 2 | sababa | 1 | Which dishes are vegan or gluten free? | 10009.3 | budget | 2 | 10637 | 0 | knowledge / hybrid | true | none / false | 10009.3 |
| 2 | sababa | 2 | What are your most popular items? | 8813.0 | provider | 1 | 3194 | 0 | - / hybrid | true | none / false | 18822.3 |
| 2 | sababa | 3 | What time do you open? | 9528.4 | done | 2 | 3754 | 0 | conversation / hybrid | true | none / false | 28350.7 |

### gpt-oss-120b (Groq)

| run | tenant | turn | message | total_ms | result | calls | in_tok | cached | route / path | mm | leg / failover | cum_ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | bytefix | 1 | What repairs do you offer? | 10004.7 | budget | 2 | 7963 | 0 | knowledge / fast | true | none / false | 10004.7 |
| 1 | bytefix | 2 | How long do repairs usually take? | 10010.3 | budget | 0 | 0 | 0 | - / fast | false | none / false | 20015.0 |
| 1 | bytefix | 3 | Do you fix water-damaged phones? | 10009.6 | budget | 0 | 0 | 0 | - / fast | false | none / false | 30024.6 |
| 1 | sababa2 | 1 | Which dishes are vegan or gluten free? | 188.3 | provider | 0 | 0 | 0 | - / fast | false | none / false | 188.3 |
| 1 | sababa2 | 2 | What are your most popular items? | 137.6 | provider | 0 | 0 | 0 | - / fast | false | none / false | 325.9 |
| 1 | sababa2 | 3 | What time do you open? | 138.1 | provider | 0 | 0 | 0 | - / fast | false | none / false | 464.0 |
| 1 | sababa | 1 | Which dishes are vegan or gluten free? | 10012.9 | budget | 0 | 0 | 0 | - / hybrid | false | none / false | 10012.9 |
| 1 | sababa | 2 | What are your most popular items? | 10008.6 | budget | 0 | 0 | 0 | - / hybrid | false | none / false | 20021.5 |
| 1 | sababa | 3 | What time do you open? | 10005.6 | budget | 2 | 3504 | 0 | conversation / hybrid | true | none / false | 30027.1 |
| 2 | bytefix | 1 | What repairs do you offer? | 10006.2 | budget | 2 | 7928 | 0 | knowledge / fast | true | none / false | 10006.2 |
| 2 | bytefix | 2 | How long do repairs usually take? | 10010.3 | budget | 0 | 0 | 0 | - / fast | false | none / false | 20016.5 |
| 2 | bytefix | 3 | Do you fix water-damaged phones? | 10010.6 | budget | 0 | 0 | 0 | - / fast | false | none / false | 30027.1 |
| 2 | sababa2 | 1 | Which dishes are vegan or gluten free? | 176.6 | provider | 0 | 0 | 0 | - / fast | false | none / false | 176.6 |
| 2 | sababa2 | 2 | What are your most popular items? | 113.0 | provider | 0 | 0 | 0 | - / fast | false | none / false | 289.6 |
| 2 | sababa2 | 3 | What time do you open? | 156.7 | provider | 0 | 0 | 0 | - / fast | false | none / false | 446.3 |
| 2 | sababa | 1 | Which dishes are vegan or gluten free? | 10013.1 | budget | 0 | 0 | 0 | - / hybrid | false | none / false | 10013.1 |
| 2 | sababa | 2 | What are your most popular items? | 10013.2 | budget | 0 | 0 | 0 | - / hybrid | false | none / false | 20026.3 |
| 2 | sababa | 3 | What time do you open? | 10008.4 | budget | 2 | 3505 | 0 | conversation / hybrid | true | none / false | 30034.7 |

### gpt-oss-20b (OpenRouter)

| run | tenant | turn | message | total_ms | result | calls | in_tok | cached | route / path | mm | leg / failover | cum_ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | bytefix | 1 | What repairs do you offer? | 10005.8 | budget | 1 | 4889 | 0 | knowledge / fast | true | none / false | 10005.8 |
| 1 | bytefix | 2 | How long do repairs usually take? | 10004.6 | budget | 1 | 4933 | 0 | knowledge / fast | true | none / false | 20010.4 |
| 1 | bytefix | 3 | Do you fix water-damaged phones? | 10005.1 | budget | 0 | 0 | 0 | - / fast | false | none / false | 30015.5 |
| 1 | sababa2 | 1 | Which dishes are vegan or gluten free? | 10005.9 | budget | 0 | 0 | 0 | - / fast | false | none / false | 10005.9 |
| 1 | sababa2 | 2 | What are your most popular items? | 10012.2 | budget | 0 | 0 | 0 | - / fast | false | none / false | 20018.1 |
| 1 | sababa2 | 3 | What time do you open? | 10008.7 | budget | 0 | 0 | 0 | - / fast | false | none / false | 30026.8 |
| 1 | sababa | 1 | Which dishes are vegan or gluten free? | 10006.0 | budget | 0 | 0 | 0 | - / hybrid | false | none / false | 10006.0 |
| 1 | sababa | 2 | What are your most popular items? | 10006.7 | budget | 0 | 0 | 0 | - / hybrid | false | none / false | 20012.7 |
| 1 | sababa | 3 | What time do you open? | 10005.7 | budget | 1 | 2625 | 0 | conversation / hybrid | true | none / false | 30018.4 |
| 2 | bytefix | 1 | What repairs do you offer? | 10007.2 | budget | 0 | 0 | 0 | - / fast | false | none / false | 10007.2 |
| 2 | bytefix | 2 | How long do repairs usually take? | 10006.2 | budget | 1 | 4933 | 4096 | knowledge / fast | true | none / false | 20013.4 |
| 2 | bytefix | 3 | Do you fix water-damaged phones? | 10006.8 | budget | 1 | 4978 | 0 | knowledge / fast | true | none / false | 30020.2 |
| 2 | sababa2 | 1 | Which dishes are vegan or gluten free? | 10005.0 | budget | 0 | 0 | 0 | - / fast | false | none / false | 10005.0 |
| 2 | sababa2 | 2 | What are your most popular items? | 10005.0 | budget | 0 | 0 | 0 | - / fast | false | none / false | 20010.0 |
| 2 | sababa2 | 3 | What time do you open? | 10007.8 | budget | 0 | 0 | 0 | - / fast | false | none / false | 30017.8 |
| 2 | sababa | 1 | Which dishes are vegan or gluten free? | 10010.4 | budget | 1 | 2538 | 0 | - / hybrid | true | none / false | 10010.4 |
| 2 | sababa | 2 | What are your most popular items? | 10007.3 | budget | 1 | 2582 | 0 | - / hybrid | true | none / false | 20017.7 |
| 2 | sababa | 3 | What time do you open? | 10007.2 | budget | 1 | 2625 | 0 | conversation / hybrid | true | none / false | 30024.9 |

## Error detail

- **Gemini**: 7 x 429 per pass, all on the `sababa` hybrid tenant; no 413 and no 5xx. Run 1 ended `sababa` turns 2 and 3 in provider refusals; run 2 ended `sababa` turn 2 in one. Retries are the provider's own bounded path; the runner never retries a turn. Free-tier quota remains the binding constraint even in this better window.
- **DeepSeek**: no 429, 413 or 5xx in either pass. 13 of 18 turns were clamped by the 10 s budget (6 in run 1, 7 in run 2). All 18 reached the model. `model_match` is false on every turn because OpenRouter served canonical `deepseek/deepseek-v4-flash-0731` while the pin is the `~deepseek/deepseek-v4-flash-latest` alias; this is the same alias effect documented in `modelcmp.md`.
- **Groq**: run 1 logged 11 x 429, 3 x 413 and 1 x 400; run 2 logged 10 x 429 and 3 x 413. Every `sababa2` request was rejected with HTTP 413, "Request too large ... tokens per minute (TPM): Limit 8000, Requested 11,274-11,560". 0 completions. The 0.4-0.5 s `sababa2` cumulative is immediate refusal, not an answer. The one 400 is the escalation-summary JSON validation rejecting prose instead of JSON.
- **gpt-oss-20b**: no 429, 413 or 5xx, and no provider refusal. 18/18 turns hit the 10 s budget. 8 of 18 turns reached the model (`model_match` true); the other 10 were clamped before a call. When a first token arrived it was at 7.1-9.2 s, leaving no room for prose inside 10 s. The model is functionally reachable but not viable at this budget.

## Cache economics

DeepSeek's cache share was 27.8% in run 1 and 7.6% in run 2 here (prior window: 3.4% then 53.1%). Cache read still equals prompt (`0.0000000049`), so caching cuts processed prompt tokens but saves no money. Gemini went 18.5% then 20.0% here (prior: 14.6% then 36.1%); no price is published, so its cost column is `n/a`. Groq read no cache. gpt-oss-20b went 0.0% then 23.2% (4,096 cached of 17,656 input tokens, all on `bytefix`); its cache-read price is half its prompt price, so caching does save money on that model.

Cost caveat: the DeepSeek, Groq and gpt-oss-20b figures are cache-adjusted list totals over only the tokens the provider billed before the 10 s clamp. For Groq and gpt-oss-20b, which completed no turns, these are the cost of aborted work, not the cost of an answer; a completed answer would be higher and cannot be derived from this run. Gemini has no published price.

## Ranking (completion first, then cumulative wait)

1. **Gemini 3.5 Flash Lite** - 14/18 done in this window, 25/36 across both windows. Completed `p50` was 4.2 s then 3.8 s; the best 3-question cumulative was `sababa2` at 9.7 s, and the hybrid `sababa` tenant still reached 28.4 s in run 2. Seven 429s per pass mean the ceiling is quota, not the model.
2. **DeepSeek V4 Flash** - 5/18 done, 8/36 across both windows. Completed `p50` was 5.0 s then 8.0 s, but 13/18 turns were budget handoffs and every tenant cumulative was 20-30 s. No rate limits. Paid, reasoning-slow, and its cache saves no money.
3. **Groq gpt-oss-120b** - 0/18 in both windows. The free tier's 8,000 TPM ceiling rejects the 11-12k-token `sababa2` prompt with HTTP 413 before any call, and the other tenants spend the budget in 429 retries. Not a working fallback at these prompt sizes.
4. **gpt-oss-20b** - 0/18. Tools and structured outputs pass, but every turn was clamped at 10 s; it is not viable for this app as configured.

Sample size: 18 turn-slots per model in this window, 36 across both windows for the three older models, 18 for gpt-oss-20b. This is one day and two quota states, not a stable benchmark; the ordering of Gemini over the paid candidates is stable in both windows, but exact ms values are not.
