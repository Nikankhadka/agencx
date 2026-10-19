# Coalesced burst measurement

Measured at `b857399` (the `--coalesce` runner change) with the production primary and the
container's configured chain, one turn per tenant, the first three corpus prompts joined by a
blank line as ONE customer message:

```
make latency LATENCY_LEGS=configured LATENCY_COALESCE=3 \
  LATENCY_MODELS=google/gemini-3.5-flash-lite LATENCY_TENANTS=all LATENCY_TURNS=1
```

Run twice back to back. `status`: **completed** = customer prose reached the customer
(`first_prose_ms` non-null); **budget** = the 10 s turn budget fired. Margin is `10000 - total_ms`.
The chain is the same two-leg chain as `prodlegs.md`: primary `models/gemini-3.5-flash-lite`
(Google AI Studio), fallback `openai/gpt-oss-120b` (Groq), failover not configured.

## Per tenant and run

| Run | Tenant | total_ms | Status | Margin (ms) | calls | Route / path | input | cached | output | Leg | failover | model_match |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | bytefix | 3358.9 | completed | 6641 | 2 | knowledge / fast | 8753 | 0 | 234 | primary | false | true |
| 1 | sababa2 | 3499.7 | completed | 6500 | 2 | knowledge / fast | 22555 | 0 | 285 | primary | false | true |
| 1 | sababa | 4808.5 | completed | 5192 | 3 | knowledge / hybrid | 14698 | 0 | 365 | primary | false | true |
| 2 | bytefix | 3411.3 | completed | 6589 | 2 | knowledge / fast | 8778 | 2026 | 265 | primary | false | true |
| 2 | sababa2 | 5724.0 | completed | 4276 | 2 | knowledge / fast | 22567 | 17739 | 332 | primary | false | true |
| 2 | sababa | 4502.8 | completed | 5497 | 3 | knowledge / hybrid | 14692 | 5750 | 354 | primary | false | true |

6/6 turns completed, 0 budget handoffs, 0 provider handoffs, failover never engaged. Run 1 is
effectively cold cache; run 2 is warm (bytefix 2026 cached, sababa2 17739, sababa 5750).

## Against the three serial turns

The comparison is the first-three cumulative from `data/prodlegs.md` (same model, same configured
chain, same prompts, `LATENCY_CONVERSATION=reuse`). Exact values verified there, not rounded from
the report:

| Tenant | 3 serial, run 1 | 1 coalesced, run 1 | Saved | 3 serial, run 2 | 1 coalesced, run 2 | Saved |
|---|---|---|---|---|---|---|
| bytefix | 10834 | 3358.9 | 69.0% | 10843 | 3411.3 | 68.5% |
| sababa2 | 14939 | 3499.7 | 76.6% | 21615 | 5724.0 | 73.5% |
| sababa | 18906 | 4808.5 | 74.6% | 14729 | 4502.8 | 69.4% |

The supervisor's rounded figures (bytefix 10.8 / 10.8, sababa2 14.9 / 21.6, sababa 18.9 / 14.7 s)
match `prodlegs.md`.

## Did one answer cover all three questions?

Yes, in all six turns. The persisted assistant row for each conversation addresses each of the
three prompts in order, separated into paragraphs; for example sababa2 run 1 lists vegan items,
then gluten-free items, then the most-liked items, then opening hours. bytefix run 1 answers
repair types, turnaround, and water damage, including the `$35` water-damage assessment from the
corpus. No turn returned only a partial answer or asked the customer to repeat a question.

## Read

- The saving is structural: one coalesced turn pays one route + retrieve + draft + inspect chain
  instead of three, so the three serial 11-19 s cumulatives collapse to 3.4-5.7 s.
- This is not the same workload as three turns: it produces ONE reply covering a burst, not three
  replies with a growing transcript. That is the product change being tested, and it is why the
  serial comparison is a ceiling, not an A/B.
- `n = 1` per tenant per run, in one provider window. Run 2's larger cache hit flatters sababa2
  (5.7 s) versus run 1 (3.5 s); both still clear the budget by more than 4 s.
- Artifacts: `coalesce-run{1,2}-google-gemini-3-5-flash-lite__<tenant>.json`; logs
  `coalesce-run{1,2}.log`. No reseed, no smoke artifact displaced (none existed for this label).
