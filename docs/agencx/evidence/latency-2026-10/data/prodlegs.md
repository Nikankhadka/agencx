# Production failover-chain measurement (configured legs, multi-turn)

Measured at `55dfe39` with `make latency LATENCY_LEGS=configured LATENCY_CONVERSATION=reuse LATENCY_MODELS=google/gemini-3.5-flash-lite LATENCY_TENANTS=all LATENCY_TURNS=5`. Primary is the model-row pin (`google/gemini-3.5-flash-lite` on Google AI Studio); the fallback and failover legs are the container `.env` chain. Five prompts per tenant in one reused conversation.

Configured chain (non-secret, recorded in every artifact as `legs_config`):

| Leg | Model | Base URL |
|---|---|---|
| primary | `models/gemini-3.5-flash-lite` (pinned from the model row) | `https://generativelanguage.googleapis.com/v1beta/openai/` |
| fallback | `openai/gpt-oss-120b` | `https://api.groq.com/openai/v1` |
| failover | (empty - not configured, so the chain is two legs) | (empty) |

`status`: **completed** = customer prose reached the customer (`first_prose_ms` non-null); **budget** = the 10 s turn budget fired; **provider** = both legs failed (429/quota) and the turn handed off before 10 s. `ttft_ms` is not carried in the latency record (the controller log line has it; the artifact does not), so it is `n/a` here and `first_token` is shown as the observable proxy. Cumulative is the sum of `total_ms` for questions 1..n.

## Run 1

| Tenant | Turn | total_ms | Status | Leg | failover_engaged | ttft_ms | first_token | calls | input | cached | route | path |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bytefix | 1 | 4072.5 | completed | primary | false | n/a | 2026.9 | 2 | 8666 | 2026 | knowledge | fast |
| bytefix | 2 | 3765.3 | completed | primary | false | n/a | 1612.9 | 2 | 8816 | 2024 | knowledge | fast |
| bytefix | 3 | 2995.8 | completed | primary | false | n/a | 1361.2 | 2 | 8853 | 2022 | knowledge | fast |
| bytefix | 4 | 3122.5 | completed | primary | false | n/a | 1380.0 | 2 | 8832 | 2019 | knowledge | fast |
| bytefix | 5 | 2784.7 | completed | primary | false | n/a | 1310.1 | 2 | 8866 | 2016 | knowledge | fast |
| sababa2 | 1 | 5439.3 | completed | primary | false | n/a | 2990.6 | 2 | 22494 | 17735 | knowledge | fast |
| sababa2 | 2 | 6202.8 | completed | primary | false | n/a | 2532.3 | 7 | 78583 | 25889 | knowledge | fast |
| sababa2 | 3 | 3297.2 | completed | primary | false | n/a | 1845.7 | 2 | 22688 | 17718 | knowledge | fast |
| sababa2 | 4 | 4266.5 | completed | primary | false | n/a | 2421.2 | 2 | 22678 | 17712 | knowledge | fast |
| sababa2 | 5 | 3467.0 | completed | primary | false | n/a | 1749.1 | 2 | 22712 | 17705 | knowledge | fast |
| sababa | 1 | 4606.9 | completed | primary | false | n/a | 3058.1 | 3 | 14571 | 5744 | knowledge | hybrid |
| sababa | 2 | 7913.6 | completed | primary | false | n/a | 3314.6 | 10 | 50861 | 1689 | knowledge | hybrid |
| sababa | 3 | 6385.6 | completed | primary | true | n/a | 1854.4 | 2 | 3974 | 0 | conversation | hybrid |
| sababa | 4 | 7907.1 | provider | fallback | true | n/a | - | 1 | 2814 | 0 | - | hybrid |
| sababa | 5 | 10009.0 | budget | fallback | true | n/a | - | 1 | 2841 | 0 | - | hybrid |

| Tenant | Completed | Budget | Provider | Cumulative 1 / 2 / 3 q (ms) | Turns racing | Leg wins |
|---|---|---|---|---|---|---|
| bytefix | 5/5 | 0 | 0 | 4072 / 7838 / 10834 | 0 | - |
| sababa2 | 5/5 | 0 | 0 | 5439 / 11642 / 14939 | 0 | - |
| sababa | 3/5 | 1 | 1 | 4607 / 12520 / 18906 | 3 | primary 1, fallback 2 |

Run 1 total: **13/15 completed**, 1 budget handoff(s), 1 provider handoff(s); race engaged on 3 turn(s); winning leg across all turns: {'primary': 13, 'fallback': 2}; race winners: {'primary': 1, 'fallback': 2}.

## Run 2

| Tenant | Turn | total_ms | Status | Leg | failover_engaged | ttft_ms | first_token | calls | input | cached | route | path |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bytefix | 1 | 3947.2 | completed | primary | false | n/a | 2482.1 | 2 | 8704 | 2026 | knowledge | fast |
| bytefix | 2 | 3533.7 | completed | primary | false | n/a | 1905.2 | 2 | 8862 | 2024 | knowledge | fast |
| bytefix | 3 | 3362.2 | completed | primary | false | n/a | 1517.9 | 2 | 8913 | 2022 | knowledge | fast |
| bytefix | 4 | 3171.6 | completed | primary | false | n/a | 1427.1 | 2 | 8909 | 2019 | knowledge | fast |
| bytefix | 5 | 3357.2 | completed | primary | false | n/a | 1615.8 | 2 | 8974 | 2017 | knowledge | fast |
| sababa2 | 1 | 4064.1 | completed | primary | false | n/a | 1921.3 | 2 | 22491 | 17735 | knowledge | fast |
| sababa2 | 2 | 9722.7 | provider | primary | true | n/a | 2189.7 | 1 | 13066 | 10186 | knowledge | fast |
| sababa2 | 3 | 7828.4 | provider | - | true | n/a | - | 0 | 0 | 0 | - | fast |
| sababa2 | 4 | 10008.6 | budget | primary | true | n/a | 9774.4 | 1 | 13079 | 10174 | knowledge | fast |
| sababa2 | 5 | 4108.9 | completed | primary | false | n/a | 2384.3 | 2 | 22677 | 17705 | knowledge | fast |
| sababa | 1 | 4577.0 | completed | primary | false | n/a | 3040.6 | 3 | 14615 | 1694 | knowledge | hybrid |
| sababa | 2 | 7460.3 | completed | primary | false | n/a | 3179.0 | 9 | 45815 | 5408 | knowledge | hybrid |
| sababa | 3 | 2691.6 | completed | primary | false | n/a | 1517.6 | 2 | 4003 | 0 | conversation | hybrid |
| sababa | 4 | 4634.1 | completed | primary | false | n/a | 2891.1 | 3 | 15136 | 0 | knowledge | hybrid |
| sababa | 5 | 10006.8 | budget | fallback | true | n/a | - | 1 | 2929 | 0 | - | hybrid |

| Tenant | Completed | Budget | Provider | Cumulative 1 / 2 / 3 q (ms) | Turns racing | Leg wins |
|---|---|---|---|---|---|---|
| bytefix | 5/5 | 0 | 0 | 3947 / 7481 / 10843 | 0 | - |
| sababa2 | 2/5 | 1 | 2 | 4064 / 13787 / 21615 | 3 | primary 2, none 1 |
| sababa | 4/5 | 1 | 0 | 4577 / 12037 / 14729 | 1 | fallback 1 |

Run 2 total: **11/15 completed**, 2 budget handoff(s), 2 provider handoff(s); race engaged on 4 turn(s); winning leg across all turns: {'primary': 13, '-': 1, 'fallback': 1}; race winners: {'primary': 2, 'none': 1, 'fallback': 1}.

## Against the single-leg multi-turn run

Same instrument, same five prompts and reused-conversation mode, but `--legs single` (fallback and failover blanked) and `deepseek/deepseek-v4.1-flash` as the primary at `3fb604a`: **4/30 completed, 26/30 handed off** (run 1 4/15; run 2 0/15).

| Run | Completed | Budget handoffs | Provider handoffs | Race engaged | Fallback completions |
|---|---|---|---|---|---|
| single-leg run 1 | 4/15 | 11 | 0 | 0 | 0 |
| single-leg run 2 | 0/15 | 15 | 0 | 0 | 0 |
| configured run 1 | 13/15 | 1 | 1 | 3 | 0 |
| configured run 2 | 11/15 | 2 | 2 | 4 | 0 |

Single-leg per tenant (completed): run 1 bytefix 2/5, sababa2 1/5, sababa 1/5; run 2 0/5 each. Single-leg cumulative 1/2/3 wall time (ms): run 1 bytefix 3233/10696/20704, sababa2 7587/17593/27599, sababa 10008/20013/29730; run 2 every tenant 10012/20019/30026, 10006/20012/30019 and 10006/20013/30019 (budget-clamped).

## Read

- The race does not rescue budget turns. The fallback leg never won a completed turn: every one of the 24 completions was served by the primary with `failover_engaged: false`, except run 1 sababa turn 3 where the primary still won after the race started. The three fallback wins were two 10 s budget handoffs and one provider handoff.
- The completion gain over the single-leg run is therefore attributable to the primary (Gemini flash-lite and its prompt caching), not to the 4 s race. The comparison is confounded: the single-leg run used a different primary and an earlier commit, so it is not a controlled A/B.
- Budget turns stayed at ~10,000 ms. Provider handoffs clustered at 7.8-9.7 s when Google returned 429 quota exhaustion (15 requests/minute free tier) and Groq returned 429 in the same turn. Bind: provider availability and per-call latency, with the 10 s turn budget still terminal.
- Artifacts: `prodlegs-run{1,2}-google-gemini-3-5-flash-lite__<tenant>.json`; logs `prodlegs-run{1,2}.log`.
