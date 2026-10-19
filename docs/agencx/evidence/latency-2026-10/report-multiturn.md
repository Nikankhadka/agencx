# Multi-turn report - reused conversations

**What the app does.** The customer surface is serialized: `send()`
returns early while `busy`, and the composer is disabled, so a second message
cannot leave the same tab until the first turn ends. There is no server queue;
each `POST /api/chat` runs one turn immediately. The agent sees the latest
`HISTORY_MESSAGES = 10` rows, including the current customer message, reloaded
every turn.

**Measured** (two runs at `3fb604a`, five turns x three tenants, deepseek): 30
turns attempted, 0 errors, 4 completed, 26 handed off at the 10 s budget (run 1
11/15, run 2 15/15). Only run 1 completed anything: bytefix 2/5, sababa2 1/5,
sababa 1/5. Budget turns clamp at ~10,000 ms, so turn order shows no slowdown.
Run 1 began cold and cache share rose from 0% to 84-99% by turn 5; warm run 2
held 97.8-99.6% for the fast tenants. Hybrid sababa was lower and non-monotone
(27.5-93.8%). Input grew about 40 tokens per turn for a fixed one-call shape,
and the 10-row cap never bound (9 rows at turn 5).

**Levers.** The data selects none. Coalescing a burst has no path to act on: the
UI already blocks a burst from one tab, and most turns fail on turn 1 regardless
of history. A queue would not shorten a turn; it would only hold arrivals, which
this instrument does not measure. A faster judge could remove a call, but 26/30
turns never reached a completed route, and the record does not separate judge
time. A server lock would add waiting to an already-serialized surface.
Streaming changes when prose appears, not `total_ms`; first model token
ranged 1.7-9.3 s on the 25 budget turns that logged one, and slice 7 stays
deferred. Any winner named here would be a hypothesis, not a measurement.
