# Generation-eval noise repeat on unchanged code (2026-10-17)

**Why.** The slice-3 pair moved generation `faithfulness` 0.7475 -> 0.7163 on a path
the slice provably cannot reach (0 of 116 replayed eval cases take the new branch,
`data/branch-exercise-probe.py`), and the drop lands 0.001 past `run_gate`'s -0.03
rule. One repeat on the identical code separates a between-window level shift from
sampling noise - or does not, which is the finding below.

## Run

- **Command** (identical to both earlier generation runs; pins from
  `data/eval-baseline.md`, no `--gate`, bytefix NOT reseeded, no `--reseed` anywhere):

```
docker compose run --rm -T -e LLM_PROVIDER=openai_compat \
  -e LLM_MODEL=deepseek/deepseek-v4.1-flash \
  -e LLM_BASE_URL=https://openrouter.ai/api/v1 \
  -e LLM_FALLBACK_MODEL= -e LLM_FALLBACK_API_KEY= \
  -e LLM_FAILOVER_MODEL= -e LLM_FAILOVER_API_KEY= \
  backend sh -c 'LLM_API_KEY="$OPENROUTER_API_KEY" python -m evals.generation_eval'
```

- **sha:** `05195b26f83b563804955bfa236846bc6d18d9ea` (`git rev-parse HEAD` on the host
  before the run). **Tree state:** `git status --porcelain` = 27 entries, all
  pre-existing (26 deleted RF-17 evidence files + untracked `.claude/`) - no tracked
  file modified, no runtime change. This order adds exactly two new files (the log and
  this note).
- **Log:** `data/eval-noise-repeat-generation.log`. **Cases:** 45 (the table reports
  `cases 45.000`, `positive_cases 33.000`, `negative_cases 12.000` - all three match the
  baseline, so the comparability guard holds; the table itself appears twice in the log,
  see the capture anomaly below).
- **Wall time:** container `StartedAt 19:41:02Z` -> `FinishedAt 20:14:18Z` = **33m16s**
  (previous generation runs: 24m18s baseline, 23m08s after).
- **Capture anomaly (does not affect the numbers):** the first `docker compose run` was
  SIGKILLed (exit 137) about 6m47s in, before its container started; the container then
  started 8s later and ran the pinned command to completion on its own (`exit=0`,
  `oom=false`). Its output was harvested with `docker logs -f`, which replays the buffer
  and then follows, so the last 12 lines are emitted twice - the tail of the case-44
  progress line, the case-45 resample line, `[45/45]` and the whole metric table appear
  at log lines 47-58 **and again** at 59-70 (line 59 truncated at the start). The 45 case
  numbers are therefore all present, but one of them (`[45/45]`) twice; the run wrote
  exactly one `eval_runs` row.
- **Other anomalies:** no traceback, no HTTP 429, no aborted case (the single
  "rate limit" string in the log is the HF Hub auth warning). The
  `llm produced malformed structured output; resampling (attempt 1/3)` path fired
  **twice** (log lines 11 and 48; the third occurrence, line 60, is the attach replay of
  line 48) against the baseline run's once - a less stable provider window, which is
  itself a hint about the drift below.

## Faithfulness across the three runs (same eval path, same pins)

| run | `eval_runs` row | created_at (UTC) | faithfulness (exact) | 4 dp |
|---|---|---|---|---|
| pre-slice baseline | `24e961dc-5463-4657-8abf-d6a2fca367a2` | 2026-10-16 13:05:56.121846 | 0.7474747474747475 | 0.7475 |
| after slice 3 | `9a4e3918-dfa1-40a1-adee-6ee0e7fc19e1` | 2026-10-16 15:14:23.241870 | 0.7163299663299664 | **0.7163** |
| **repeat (this run)** | `f11f79f9-af16-46e2-a33b-85431f8bfa73` | 2026-10-16 20:14:17.354734 | 0.7181818181818181 | **0.7182** |

Pairwise spreads:

| pair | faithfulness spread |
|---|---|
| repeat - after (identical code, same tree) | **+0.0019** (exact +0.0018518518518517713) |
| after - baseline (the drift under test) | -0.0311 |
| repeat - baseline | -0.0293 |

Same windows, the other two generation metrics, for scale:

| metric | baseline | after | repeat | repeat - after | after - baseline |
|---|---|---|---|---|---|
| answer_relevancy | 0.7356 | 0.8025 | 0.7535 | -0.0490 | +0.0668 |
| citation_faithfulness | 0.3207 | 0.3692 | 0.3283 | -0.0409 | +0.0485 |
| faithfulness | 0.7475 | 0.7163 | 0.7182 | +0.0019 | -0.0311 |
| refusal_accuracy | 0.000 | 0.000 | 0.000 | 0 | 0 |
| negative_cases | 12 | 12 | 12 | 0 | 0 |

## Verdict

**No - the 0.0311 baseline -> after drift is NOT inside the identical-code spread: the
two post-change runs agree to 0.0019 on faithfulness while both sit ~0.03 below the
baseline window, so on this evidence the drop is a between-window level shift, not
sampling noise the tolerance can absorb.** The change still cannot cause it (0 of 116
replayed eval cases take the new path, and the 43 P-3 / 2 structured paths it does take
are behaviourally identical between the two shas), so the leading explanation is
provider-side drift across the two windows - the repeat window was also 10 minutes
slower per run and resampled malformed output twice against the baseline's once. That
explanation is *not* proven: there is one sample in the baseline window, so a
re-measurement there is needed before the level shift is called environmental.

This is what `report-slice-3.md` now records: the -0.0311 is written as a between-window
level shift, not as "this harness's noise" (the within-window spread on faithfulness is
~0.002, and the gate's FAIL is carried as an open, unexplained item). The two judge-heavy
metrics behave the other way - their within-window spread (0.041-0.049) is comparable to
their own baseline->after moves (0.048-0.067), so those two moves are within noise.

## `eval_runs` row this run creates

- New row `f11f79f9-af16-46e2-a33b-85431f8bfa73` (bytefix / generation,
  `git_sha` empty as always in-container), created **after** both existing generation
  rows, so the generation order is: baseline 13:05:56 -> after 15:14:23 -> repeat
  20:14:17.
- Consequence for a later `run_gate`: it pairs the **two most recent** rows, which are
  now **both post-change** - repeat vs after = `+0.0019` -> PASS. The gate would
  therefore no longer fail generation, but that is a pairing artefact: the
  baseline -> after comparison (`-0.0311`) is still the one this measurement set out to
  explain, and it is only reachable from `data/eval-after-slice3-env.txt` and this file
  from now on.
- No reseed was performed; bytefix is still `e9139d84-0e9f-4282-9af6-e0dc9bf4b56e` and
  all six earlier rows are intact.
