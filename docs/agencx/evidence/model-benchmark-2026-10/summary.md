# Model benchmark

- Command: `python -m evals.model_benchmark --models all --report-only --out /evidence`
- Commit: `unknown` (MODEL_BENCHMARK_COMMIT)
- Report mode: `aggregated_from_raw` (6 raw artifacts)
- Generated: 2026-10-22T05:48:11Z
- Suite: `all` (repeats override: n/a, limit: n/a)
- Judge: `anthropic/claude-haiku-5.5` (fixed, never a candidate)
- Second judge: `openai/gpt-6-luna` (agreement checks only)
- Pricing: not_fetched (fetched n/a)

## Capability gate

| family | candidate | api model | route | qualified | first failure |
|---|---|---|---|---|---|
| deepseek | openrouter/deepseek-v4.1-flash | deepseek/deepseek-v4.1-flash | openrouter | yes | - |
| gemini | google-native/gemini-3.5-flash | models/gemini-3.5-flash | google_native | no | RateLimitError: Error code: 429 - [{'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20, model: gemini-3.6-flash\nPlease retry in 3h7m43.330187667s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}, {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier', 'quotaDimensions': {'location': 'global', 'model': 'gemini-3.6-flash'}, 'quotaValue': '20'}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '11263s'}]}}] |
| gemini | google-native/gemini-3.5-flash-lite | models/gemini-3.5-flash-lite | google_native | yes | - |
| gemma | openrouter/gemma-4-26b-a4b-it | google/gemma-4-26b-a4b-it | openrouter | yes | - |
| mistral | openrouter/mistral-small-3.2-24b-instruct | mistralai/mistral-small-3.2-24b-instruct | openrouter | yes | - |
| qwen | openrouter/qwen3.8-27b | qwen/qwen3.8-27b | openrouter | yes | - |

## Quality by criterion

| candidate | suite | criterion | mean | 95% CI | n | interval |
|---|---|---|---|---|---|---|
| openrouter/deepseek-v4.1-flash | generation | faithfulness | 0.925 | 0.882 - 0.959 | 33 | bootstrap |
| openrouter/deepseek-v4.1-flash | generation | answer_relevancy | 0.807 | 0.786 - 0.829 | 33 | bootstrap |
| openrouter/deepseek-v4.1-flash | generation | citation_faithfulness | 0.869 | 0.768 - 0.944 | 33 | bootstrap |
| openrouter/deepseek-v4.1-flash | generation | fact_coverage | 0.881 | 0.778 - 0.962 | 33 | bootstrap |
| openrouter/deepseek-v4.1-flash | generation | refusal_correct | 0.000 | 0.000 - 0.243 | 12 | wilson |
| openrouter/deepseek-v4.1-flash | generation | refusal_semantic | 0.917 | 0.646 - 0.985 | 12 | wilson |
| openrouter/deepseek-v4.1-flash | trajectory | tool_correctness | 0.654 | 0.518 - 0.768 | 52 | wilson |
| openrouter/deepseek-v4.1-flash | trajectory | step_efficiency | 0.954 | 0.918 - 0.987 | 52 | bootstrap |
| openrouter/deepseek-v4.1-flash | trajectory | persona_quality | 0.800 | 0.400 - 1.000 | 5 | bootstrap |
| openrouter/deepseek-v4.1-flash | injection | injection | 0.967 | 0.833 - 0.994 | 30 | wilson |
| openrouter/gemma-4-26b-a4b-it | generation | faithfulness | 0.966 | 0.927 - 0.995 | 33 | bootstrap |
| openrouter/gemma-4-26b-a4b-it | generation | answer_relevancy | 0.825 | 0.802 - 0.849 | 33 | bootstrap |
| openrouter/gemma-4-26b-a4b-it | generation | citation_faithfulness | 0.970 | 0.924 - 1.000 | 33 | bootstrap |
| openrouter/gemma-4-26b-a4b-it | generation | fact_coverage | 0.904 | 0.798 - 0.980 | 33 | bootstrap |
| openrouter/gemma-4-26b-a4b-it | generation | refusal_correct | 0.000 | 0.000 - 0.243 | 12 | wilson |
| openrouter/gemma-4-26b-a4b-it | generation | refusal_semantic | 0.917 | 0.646 - 0.985 | 12 | wilson |
| openrouter/gemma-4-26b-a4b-it | trajectory | tool_correctness | 0.577 | 0.442 - 0.701 | 52 | wilson |
| openrouter/gemma-4-26b-a4b-it | trajectory | step_efficiency | 0.994 | 0.981 - 1.000 | 52 | bootstrap |
| openrouter/gemma-4-26b-a4b-it | trajectory | persona_quality | 0.600 | 0.200 - 1.000 | 5 | bootstrap |
| openrouter/gemma-4-26b-a4b-it | injection | injection | 0.933 | 0.787 - 0.982 | 30 | wilson |
| openrouter/mistral-small-3.2-24b-instruct | generation | faithfulness | 0.951 | 0.907 - 0.985 | 33 | bootstrap |
| openrouter/mistral-small-3.2-24b-instruct | generation | answer_relevancy | 0.841 | 0.809 - 0.869 | 33 | bootstrap |
| openrouter/mistral-small-3.2-24b-instruct | generation | citation_faithfulness | 0.856 | 0.735 - 0.955 | 33 | bootstrap |
| openrouter/mistral-small-3.2-24b-instruct | generation | fact_coverage | 0.904 | 0.818 - 0.970 | 33 | bootstrap |
| openrouter/mistral-small-3.2-24b-instruct | generation | refusal_correct | 0.000 | 0.000 - 0.243 | 12 | wilson |
| openrouter/mistral-small-3.2-24b-instruct | generation | refusal_semantic | 0.500 | 0.254 - 0.746 | 12 | wilson |
| openrouter/mistral-small-3.2-24b-instruct | trajectory | tool_correctness | 0.500 | 0.369 - 0.631 | 52 | wilson |
| openrouter/mistral-small-3.2-24b-instruct | trajectory | step_efficiency | 0.983 | 0.963 - 1.000 | 52 | bootstrap |
| openrouter/mistral-small-3.2-24b-instruct | trajectory | persona_quality | 1.000 | 1.000 - 1.000 | 5 | bootstrap |
| openrouter/mistral-small-3.2-24b-instruct | injection | injection | 0.567 | 0.392 - 0.726 | 30 | wilson |
| openrouter/qwen3.8-27b | generation | faithfulness | 0.913 | 0.854 - 0.960 | 33 | bootstrap |
| openrouter/qwen3.8-27b | generation | answer_relevancy | 0.803 | 0.780 - 0.825 | 33 | bootstrap |
| openrouter/qwen3.8-27b | generation | citation_faithfulness | 0.917 | 0.836 - 0.977 | 33 | bootstrap |
| openrouter/qwen3.8-27b | generation | fact_coverage | 0.866 | 0.760 - 0.949 | 33 | bootstrap |
| openrouter/qwen3.8-27b | generation | refusal_correct | 0.000 | 0.000 - 0.243 | 12 | wilson |
| openrouter/qwen3.8-27b | generation | refusal_semantic | 0.958 | 0.699 - 0.996 | 12 | wilson |
| openrouter/qwen3.8-27b | trajectory | tool_correctness | 0.635 | 0.499 - 0.752 | 52 | wilson |
| openrouter/qwen3.8-27b | trajectory | step_efficiency | 0.910 | 0.860 - 0.955 | 52 | bootstrap |
| openrouter/qwen3.8-27b | trajectory | persona_quality | 0.600 | 0.200 - 1.000 | 5 | bootstrap |
| openrouter/qwen3.8-27b | injection | injection | 0.967 | 0.833 - 0.994 | 30 | wilson |

## Safety and money

| candidate | injection pass | injection n | tool correctness | trajectory n | refusal accuracy | semantic refusal | money violations |
|---|---|---|---|---|---|---|---|
| openrouter/deepseek-v4.1-flash | 0.967 | 30 | 0.654 | 52 | 0.000 | 0.917 | 0 |
| google-native/gemini-3.5-flash | n/a | 0 | n/a | 0 | n/a | n/a | 0 |
| google-native/gemini-3.5-flash-lite | n/a | 0 | n/a | 0 | n/a | n/a | 0 |
| openrouter/gemma-4-26b-a4b-it | 0.933 | 30 | 0.577 | 52 | 0.000 | 0.917 | 0 |
| openrouter/mistral-small-3.2-24b-instruct | 0.567 | 30 | 0.500 | 52 | 0.000 | 0.500 | 0 |
| openrouter/qwen3.8-27b | 0.967 | 30 | 0.635 | 52 | 0.000 | 0.958 | 0 |

## Operational

| candidate | turns scored | turn p50 ms | turn p95 ms | calls p50 | calls p95 | error rate | judge errors | input tokens | output tokens | cache share | cost USD |
|---|---|---|---|---|---|---|---|---|---|---|---|
| openrouter/deepseek-v4.1-flash | 172 | 6242.3 | 32418.6 | 2.0 | 4.0 | 0.000 | 0 | 1654719 | 308969 | 0.446 | 0.650329 |
| google-native/gemini-3.5-flash | 0 | n/a | n/a | n/a | n/a | 0.000 | 0 | 0 | 0 | 0.000 | n/a |
| google-native/gemini-3.5-flash-lite | 0 | n/a | n/a | n/a | n/a | 0.000 | 0 | 0 | 0 | 0.000 | n/a |
| openrouter/gemma-4-26b-a4b-it | 172 | 4102.0 | 127042.9 | 2.0 | 2.0 | 0.000 | 0 | 1508924 | 23894 | 0.490 | 0.096399 |
| openrouter/mistral-small-3.2-24b-instruct | 172 | 7310.2 | 17310.6 | 2.0 | 2.0 | 0.000 | 0 | 1572171 | 37023 | 0.005 | 0.156647 |
| openrouter/qwen3.8-27b | 172 | 17821.9 | 82641.1 | 2.0 | 4.0 | 0.000 | 0 | 1817508 | 471776 | 0.305 | 0.697383 |

## Verdict vs thresholds

Gates: faithfulness 0.85, answer_relevancy 0.85, citation_faithfulness 0.85, fact_coverage 0.8, tool_correctness 0.9, injection 0.8, money_violations 0.

| candidate | verdict | reasons |
|---|---|---|
| openrouter/deepseek-v4.1-flash | FAIL | answer_relevancy 0.8072912712232382 below gate 0.85; citation_faithfulness mean 0.869 meets 0.85 but its 95% interval reaches 0.768; fact_coverage mean 0.881 meets 0.8 but its 95% interval reaches 0.778; tool_correctness 0.6538461538461539 below gate 0.9 |
| google-native/gemini-3.5-flash | FAIL | capability gate: RateLimitError: Error code: 429 - [{'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20, model: gemini-3.6-flash\nPlease retry in 3h7m43.330187667s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}, {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier', 'quotaDimensions': {'location': 'global', 'model': 'gemini-3.6-flash'}, 'quotaValue': '20'}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '11263s'}]}}]; suites not scored: generation, trajectory, injection; faithfulness was not scored (gate 0.85); answer_relevancy was not scored (gate 0.85); citation_faithfulness was not scored (gate 0.85); fact_coverage was not scored (gate 0.8); tool_correctness was not scored (gate 0.9); injection was not scored (gate 0.8) |
| google-native/gemini-3.5-flash-lite | FAIL | suites not scored: generation, trajectory, injection; faithfulness was not scored (gate 0.85); answer_relevancy was not scored (gate 0.85); citation_faithfulness was not scored (gate 0.85); fact_coverage was not scored (gate 0.8); tool_correctness was not scored (gate 0.9); injection was not scored (gate 0.8) |
| openrouter/gemma-4-26b-a4b-it | FAIL | answer_relevancy 0.8250314878520235 below gate 0.85; fact_coverage mean 0.904 meets 0.8 but its 95% interval reaches 0.798; tool_correctness 0.5769230769230769 below gate 0.9; injection mean 0.933 meets 0.8 but its 95% interval reaches 0.787 |
| openrouter/mistral-small-3.2-24b-instruct | FAIL | answer_relevancy 0.8411397461967686 below gate 0.85; citation_faithfulness mean 0.856 meets 0.85 but its 95% interval reaches 0.735; tool_correctness 0.5 below gate 0.9; injection 0.5666666666666667 below gate 0.8 |
| openrouter/qwen3.8-27b | FAIL | answer_relevancy 0.8032884754587792 below gate 0.85; citation_faithfulness mean 0.917 meets 0.85 but its 95% interval reaches 0.836; fact_coverage mean 0.866 meets 0.8 but its 95% interval reaches 0.760; tool_correctness 0.6346153846153846 below gate 0.9 |

## Second-judge agreement

| candidate | cases sampled | labels | raw agreement | Cohen's kappa |
|---|---|---|---|---|
| openrouter/deepseek-v4.1-flash | 12 | 43 | 0.930 | 0.628 |
| google-native/gemini-3.5-flash | 0 | 0 | n/a | n/a |
| google-native/gemini-3.5-flash-lite | 0 | 0 | n/a | n/a |
| openrouter/gemma-4-26b-a4b-it | 13 | 35 | 1.000 | 1.000 |
| openrouter/mistral-small-3.2-24b-instruct | 13 | 34 | 0.971 | 0.841 |
| openrouter/qwen3.8-27b | 13 | 47 | 1.000 | 1.000 |

## Limitations

- Candidates are exactly the config rows. A model that could not be measured is recorded with its exact error rather than omitted.
- Rows whose provider publishes no price report cost as `null`, never zero.
- Judge calls are metered separately and excluded from candidate cost and latency. Costs are cache-adjusted when the provider publishes a cache-read price.
- Repeats of one case are averaged into a single per-case observation before any statistic is computed, so `n` is the distinct-case count, not the number of generation calls.
- Rates use a Wilson interval; means use a seeded percentile bootstrap (1000 resamples). A criterion backed by fewer than five distinct cases cannot make a candidate PASS, and a gated criterion that was never scored cannot PASS.
- Judges are fixed and independent of every candidate. A judge call that fails is counted in `judge errors` and forces CONDITIONAL.
- A suite that produced no case records is a hard failure for the candidate, not a skipped line.
- Refusal is reported twice. `refusal accuracy` is the strict exact-match metric against the refusal constant. `semantic refusal` is a judge's view of whether the assistant withheld the requested information, so a correct refusal in the model's own words counts. Only the strict metric is compared with a gate; the semantic column is narrative evidence and does not change a verdict.
- Money scoring allows the tenant catalog's own prices. A draft that quotes a real catalog row is not inventing a figure.
- No API key or full base URL is written to any artifact.
