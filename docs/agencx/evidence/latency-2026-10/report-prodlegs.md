# Production failover chain - multi-turn

**Measured** at `55dfe39`: `google/gemini-3.5-flash-lite` as the pinned primary with the container's configured
chain behind it - Groq `openai/gpt-oss-120b` fallback, no failover leg (model empty). Two runs, three tenants,
five fixed prompts, one reused conversation per tenant.

**Result.** 24/30 turns completed (run 1 13/15, run 2 11/15), with 3 budget and 3 provider handoffs. The
single-leg control (deepseek, `3fb604a`) completed 4/30. But the gain is not the race: 23 of the 24 completions
never engaged it. The race engaged on 7 turns and rescued none - the primary won 3 (one completion), the
fallback won 3 (two budget handoffs, one provider handoff), one had no winner. The fallback never served a
completed turn.

**Which leg wins.** The primary, on every completion. The fallback appeared only when Google was backing off a
429; Groq then 429'd in the same turn, so the turn ended at 7.8-9.7 s as a provider handoff or clamped at the
10 s budget.

**Verdict.** The 4 s race does not rescue the budget turns. It is insurance against a slow primary, not a
latency fix: when the primary is slow the fallback is usually slow or rate-limited too, and a turn still needs
2-3 serial calls. The gain over single-leg comes from the faster primary and prompt caching (about 2.0k cached
tokens on bytefix, 17.7k on sababa2's fast path, 0 on hybrid sababa), and that comparison is confounded by a
different primary model and commit.

**Binding constraint.** Provider availability and per-call latency under the 10 s turn budget - Google
free-tier 429s (15 requests/minute) and Groq 429s - not the failover policy. Configuring the empty failover leg
is the one lever this data selects.
