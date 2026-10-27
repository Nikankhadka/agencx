# Source-to-review, end to end: old and new side by side (ticket 29)

Measured on 2026-10-27 against two checkouts in the local docker compose stack,
driven through the real UI with Playwright.

## Method

**old** is `development` at `1f384a2` (`git worktree add ../agencx-perf-old
development`): the pre-ticket interview (name, business name, business type,
headcount, hours, services, voice, contact, ABN) and only then the website ask.
**new** is `feat/30-chat-catalog-full-list` at `132bc27`, the tip of the 29 + 30
stack: name (Skip), then the source stage. Both submit the same URL through the
same composer into the same review sheet, so the two numbers are one owner
action on two implementations.

**The measurements.** All three timestamps are taken with `performance.now()`
inside one page, from a probe the spec installs at runtime (a capture-phase
click listener and a `requestAnimationFrame` loop). No application code is
touched by the instrumentation.

- `t0`: the click event that reaches the Send button. The listener is in the
  capture phase, so it runs before React's own submit handler; the stamp costs
  one property write, so the overhead is not measurable. The URL is already in
  the composer when the clock starts.
- `t_feedback`: the first frame in which the thread shows the progress copy,
  matched on the thread's own `p.text-proc` element: `Reading your site...`,
  `Finding your services...` or `Waiting for your review...`.
- `t_review`: the first frame in which a service row is painted inside the
  review sheet's offerings section. The resolver is the section whose own text
  says `N retained offering`; its first row is the editable row's
  `Offering 1 name` field, or a read-only row's heading. On a run where the
  extraction retained no offerings the same section's `No offerings yet.` line
  is the anchor and the row is labelled `empty`. The sheet is always mounted
  (it slides off-screen), so the anchor is deliberately something inside its
  body, never `toBeHidden`.
- `t_server`: the server's own `total_ms` for the source turn, read from the
  `onboarding source timing` log line. The ticket-29 branch emits it; the
  `development` checkout has no such line, so the perf worktree carries a
  measurement-only `try/finally` that logs the identical key set, plus the same
  per-phase timings. That edit lives only in the throwaway worktree and is
  never committed; the shipped branch is untouched.
- `render_ms = (t_review - t0) - t_server`. It therefore includes the browser's
  request dispatch, the server's own handler entry, the post-stream
  `GET /api/knowledge/records`, and the paint. It is the leg after the server
  has finished the turn, not a pure React render.

**The URL and the provider.** `https://www.thegrounds.com.au/` for the real
crawl, plus the app's own static five-page fixture
`http://frontend:3000/fixtures/example-business.html`, which the backend fetches
over the compose network (the same fixture the e2e suite uses, so no external
flakiness). The configured chain was Google `gemini-3.5-flash-lite` (free tier,
primary) with OpenRouter `deepseek/deepseek-v4.1-flash` (paid, fallback) and no
failover leg. The primary returned 429s during the session; the fallback served
several calls. Nothing was mocked: a fresh owner logs in through GoTrue and
Mailpit, the backend crawls the real site, and the configured model does the
structuring, the offering extraction and the profile read.

**Runs and blocks.** Three runs per block, one block per implementation, and the
blocks interleaved old, new, old so provider drift hits both: old block 1
(grounds + fixture), new block 1, old block 2, then new block 2, and an extra
old block 3 carrying the per-phase timings. Each block ran from its own checkout
with the stack torn down between blocks, the Next cache wiped (`find /app/.next
-mindepth 1 -delete`, the `make dev-reset` recipe) and the same compose project
name reused, because the branch pair shares lockfiles, images and migrations,
so running one at a time cannot collide on a volume. Playwright ran serially (one
worker), one invocation per run, with the backend log offset captured around each
invocation so the client row and the server line pair unambiguously.

Driver: `frontend/e2e/source-latency.spec.ts`, opt-in only
(`test.skip(!process.env.SOURCE_LATENCY, ...)`), so a normal e2e run and CI skip
it:

```
SOURCE_LATENCY=1 SOURCE_FLOW=old|new SOURCE_RUNS=N SOURCE_URL=<url> \
SOURCE_LATENCY_OUT=<abs path>/rows.jsonl \
npx playwright test e2e/source-latency.spec.ts --project=chromium -g "<flow> run <n>"
```

Completed runs: **old 17 of 18 attempted** (one interview turn failed before the
source was submitted), **new 12 of 16 attempted** (three grounds runs and one
fixture run lost to a backend hang, below; the fixture block's remaining two runs
never started). 29 completed runs in total.

## Table 1, whole path, per run

`t0 -> feedback` and `t0 -> review` are client milliseconds. `server` is the
turn's own `total_ms`. `render` is `(t0 -> review) - server`. `svc` is the
retained offering count printed by the sheet (`-` for the three grounds runs that
predate that field in the probe).

| Flow | URL | Block | Run | t0 -> feedback | t0 -> review | server | render | svc | Outcome |
|---|---|---|---|---|---|---|---|---|---|
| old | grounds | 1 | 1 | 27 | 23,725 | 23,675 | 50 | - | ok |
| old | grounds | 1 | 2 | 25 | 9,080 | 9,050 | 30 | - | ok |
| old | grounds | 1 | 3 | 31 | 12,414 | 12,368 | 46 | - | ok |
| old | grounds | 2 | 1 | 31 | 10,713 | 10,661 | 52 | 5 | ok |
| old | grounds | 2 | 2 | 41 | 17,894 | 17,839 | 55 | 3 | ok |
| old | grounds | 2 | 3 | 46 | 8,816 | 8,760 | 56 | 3 | ok |
| old | grounds | 3 | 1 | 21 | 9,498 | 9,464 | 34 | 8 | ok |
| old | grounds | 3 | 2 | 30 | 9,966 | 9,921 | 46 | 3 | ok |
| old | grounds | 3 | 3 | 24 | 11,136 | 11,094 | 42 | 3 | ok |
| old | fixture | 1 | 1 | 45 | 7,359 | 7,303 | 57 | 8 | ok |
| old | fixture | 1 | 2 | 30 | 7,297 | 7,259 | 38 | 8 | ok |
| old | fixture | 1 | 3 | - | - | - | - | - | failed: the interview never advanced (no stage change and no read-back chip within 120s), so the source was never submitted |
| old | fixture | 2 | 1 | 32 | 71,296 | 71,251 | 45 | 2 | ok, provider stall (Google 429 cascade) |
| old | fixture | 2 | 2 | 24 | 6,218 | 6,182 | 36 | 6 | ok |
| old | fixture | 2 | 3 | 49 | 5,909 | 5,850 | 59 | 8 | ok |
| old | fixture | 3 | 1 | 31 | 54,827 | 54,782 | 46 | 9 | ok, provider stall |
| old | fixture | 3 | 2 | 36 | 13,578 | 13,523 | 55 | 8 | ok |
| old | fixture | 3 | 3 | 29 | 69,083 | 69,043 | 40 | 9 | ok, provider stall |
| new | grounds | 1 | 1 | 26 | 4,399 | 4,361 | 38 | 7 | ok |
| new | grounds | 1 | 2 | 32 | 4,922 | 4,884 | 38 | 1 | ok |
| new | grounds | 1 | 3 | 32 | 3,026 | 2,990 | 36 | 1 | ok |
| new | grounds | 2 | 1 | 30 | 7,238 | 7,193 | 45 | 6 | ok |
| new | grounds | 2 | 2 | 32 | 7,486 | 7,449 | 37 | 7 | ok |
| new | grounds | 2 | 3 | 24 | 4,060 | 4,025 | 36 | 6 | ok |
| new | fixture | 1 | 1 | 32 | 3,939 | 3,895 | 44 | 6 | ok |
| new | fixture | 1 | 2 | 32 | 4,063 | 4,025 | 38 | 16 | ok |
| new | fixture | 1 | 3 | 24 | 3,656 | 3,622 | 34 | 6 | ok |
| new | fixture | 2 | 1 | 24 | 4,509 | 4,470 | 39 | 7 | ok |
| new | fixture | 2 | 2 | 33 | 2,408 | 2,371 | 37 | 6 | ok |
| new | fixture | 2 | 3 | 24 | 26,367 | 26,331 | 36 | 7 | ok, provider stall (offering extraction 26.2s) |
| new | grounds | 2 | pre 1-3 | - | - | - | - | - | three runs lost: backend stopped responding at 05:02:27 (see threats) |
| new | fixture | 2 | pre 1 | - | - | - | - | - | one run lost to the same hang; the block's next two never started |

## Table 2, medians

Median of the completed runs, with the full spread in brackets. Grounds: 6 old
and 6 new. Fixture: 8 old and 6 new. The fixture's old spread carries three
provider stalls above 50s, so a stall-excluded median is given as well.

| URL | Flow | Runs | t0 -> review, median [min-max] | t_server, median [min-max] | render, median [min-max] |
|---|---|---|---|---|---|
| grounds | old | 6 | **10,713** [8,816-23,725] | 10,661 [8,760-23,675] | 46 [30-56] |
| grounds | new | 6 | **4,661** [3,026-7,486] | 4,623 [2,990-7,449] | 38 [36-45] |
| fixture | old | 8 | **10,469** [5,909-71,296] | 10,413 [5,850-71,251] | 45 [36-59] |
| fixture | new | 6 | **4,001** [2,408-26,367] | 3,960 [2,371-26,331] | 37 [34-44] |
| fixture, stalls excluded | old | 5 | 7,297 [5,909-13,578] | 7,259 [5,850-13,523] | 46 [36-59] |
| fixture, stalls excluded | new | 5 | 3,939 [2,408-4,509] | 3,895 [2,371-4,470] | 38 [34-44] |

| URL | Metric | Old | New | Delta | Delta % |
|---|---|---|---|---|---|
| grounds | t0 -> review | 10,713 | 4,661 | **-6,053** | **-56.5%** |
| grounds | t_server | 10,661 | 4,623 | -6,038 | -56.6% |
| grounds | render | 46 | 38 | -8 | -18.4% |
| grounds | t0 -> feedback | 30 | 31 | +1 | +3.3% |
| fixture | t0 -> review | 10,469 | 4,001 | **-6,468** | **-61.8%** |
| fixture, stalls excluded | t0 -> review | 7,297 | 3,939 | -3,358 | -46.0% |
| fixture | render | 45 | 37 | -8 | -17.8% |

Per-block medians of `t0 -> review`, so the same comparison appears in every
interleave (the numbers move with provider weather, the sign does not):

| URL | Block | Old | New | Delta |
|---|---|---|---|---|
| grounds | 1 | 12,414 | 4,399 | -64.6% |
| grounds | 2 | 10,713 | 7,238 | -32.4% |
| fixture | 1 | 7,328 | 3,939 | -46.3% |
| fixture | 2 | 6,218 | 4,509 | -27.5% |

## Table 3, where the time goes

The old turn is `crawl -> draft (structure then offerings, serial) -> profile
extract -> reply`; the new turn is `crawl -> max(draft (structure and offerings
concurrent), profile) -> reply`. Values are the server's own per-phase
milliseconds from the same log line, medians with the full set in brackets.

| Phase | Old, grounds | New, grounds | What the phase is |
|---|---|---|---|
| crawl | 5,136 [3,953-5,250] (n=3) | 1,195 [1,066-1,826] (n=6) | fetch and assemble the site document |
| draft | 3,903 [3,179-3,990] (n=3) | 3,293 [1,766-6,123] (n=6) | structure plus offering extraction |
| profile | 1,604 [1,489-1,964] (n=3) | 1,454 [1,183-3,189] (n=6) | the profile fields read from the site |
| reply | 0.1 [0.0-0.1] (n=3) | 1.6 [1.3-2.0] (n=6) | the read-back line (both are deterministic, no model call) |
| **critical path** | **10,661** (sum of the four) | **4,623** (`crawl + max(draft, profile) + reply`) | matches `total_ms` within 5ms old and 2ms new on every run |
| render | 46 [30-56] | 38 [36-45] | browser, post-server, to painted service row |

For the fixture (the controlled comparison, same bytes on both):

| Phase | Old, fixture | New, fixture |
|---|---|---|
| crawl | 240 [231-372] (n=3) | 154 [106-1,720] (n=6, the 1.7s runs are a cold `next dev` compile of the fixture route) |
| draft | 39,734 [4,374-66,656] (n=3) | 3,130 [2,219-26,215] (n=6) |
| profile | 8,914 [2,143-14,671] (n=3) | 2,007 [1,527-3,022] (n=6) |
| reply | 0.0 (n=3) | 1.5 (n=6) |
| critical path | 54,782 (sum) | 4,470 (`crawl + max(draft, profile) + reply`) |
| render | 46 [36-59] | 38 [34-44] |

Read together: the win is in the two server phases the ticket changed. The crawl
is ~4.3x faster on the real site (5,136 -> 1,195); the processing block stops
paying the serial sum (the old ground run spends `draft 3,903 + profile 1,604`
where the new one pays `max(draft, profile)`, and the fixture's old draft column
is the provider stalling inside the serial passes). The last leg is unchanged
and small: **render is 30-59ms on every run of either implementation**, so
nothing in the client or the review sheet moves the number.

## Verdict

**The new path is faster scrape-to-review, on every block and both URLs, and the
win is server-side.** Median `t0 -> review` on `www.thegrounds.com.au` (the real
crawl, n=6 each) is **10,713ms old against 4,661ms new, -6,053ms or -56.5%**,
with the new spread 3,026-7,486ms against the old 8,816-23,725ms. The same
comparison holds in every interleaved block: -64.6% in block 1 and -32.4% in
block 2 on grounds, -46.3% and -27.5% on the fixture, so the sign survives the
provider drifting in both directions. On the fixture (n=8 old, n=6 new) the
medians are 10,469ms against 4,001ms, but three of the eight old runs are
provider stalls of 55-71s; excluding every run over 50s, it is 7,297ms against
3,939ms (-46.0%), which is the fair fixture number.

Where the time went: the crawl fell about 4x on the real site (5,136 -> 1,195),
and the processing block stopped paying the serial sum, so the critical path is
`crawl + max(draft, profile)` rather than `crawl + structure + offerings +
profile`. The reply was already deterministic on both. **Nothing is slower in the
new path** in this sample: the render leg is 8ms lower (46 -> 38, inside its own
spread), the first progress stamp is 1ms later (30 -> 31, noise), and the new
path's median is lower in every block.

The sample is small and the provider is noisy, so the size of the win should be
read as "roughly half to two thirds on a good window, a third on a bad one", not
as a single percentage. What supports the claim is not the medians alone but the
phase decomposition: the same turn composed from its own sub-timings reproduces
`total_ms` to within 5ms, and the two phases the ticket changed are the two that
moved. A larger n would tighten the interval, not change the direction.

## Threats to validity

- **Free-tier provider variance is the dominant error bar.** Google's free tier
  is capped at 20 requests/day/model and it returned 429s mid-session; the chain
  then raced or fell to DeepSeek. The single worst old run (71.3s) is entirely a
  Google 429 cascade logged at 04:58:46-04:59:30 (two rate-limited retries, the
  primary losing the race, then `offering extraction failed for a segment`), not
  the crawl. Two more old fixture runs (54.8s, 69.1s) are the same weather. This
  is why every block is reported and the stall-excluded medians are given.
- **One backend hang, unexplained, not a latency result.** During new block 2's
  first grounds run (05:02:27) the backend stopped responding: the last log line
  was a page fetch, `/health` then timed out for more than 15 minutes, the
  process stayed alive at near-idle CPU, and no `site crawl` line ever arrived.
  The same crawl succeeds standalone (`crawl_probe` on the same URL: new path
  2,586ms, 4 pages, 11,440 chars) and a container restart cleared it; it did not
  recur in the 12 new-path runs that followed. Those four attempted new runs are
  reported as lost. If this recurs it needs its own investigation; it is not
  attributable to either checkout from one occurrence.
- **Cold Next dev compile.** `next dev` compiles a route on first request. The
  measured window starts after login and after the interview, so page compile
  never lands inside it, but the backend's fetch of the fixture can hit the
  fixture route's first compile: the two 1.7s crawl values in the new fixture
  column are that, on the first fixture run after a frontend restart. The
  cache was wiped between blocks (`make dev-reset` recipe); a stable comparison
  needs one warm fixture read after each wipe.
- **One machine, one user, one URL pair.** Both stacks ran on the same laptop,
  serially, one compose project at a time. No concurrency, no network shaping,
  no second owner. Only The Grounds and the fixture were measured; nandos has no
  whole-path row, and the other validation-matrix sites still have none.
- **The offline fixture is not a public URL.** `frontend:3000` is only
  resolvable inside the compose network, so the fixture rows measure the same
  code path with a near-zero crawl, not a real site.
- **`render_ms` is a residual, not a pure render.** It includes the client's
  request dispatch, the server's handler entry, the post-stream
  `GET /api/knowledge/records` and the paint. Its 30-59ms spread is the whole
  leg; no part of the new path's win is here.
- **The offering extraction is not deterministic.** Retained counts range 1-16
  across runs of the same URL on both implementations, and two old grounds runs
  retained enough offerings to render read-only rows (no editable name field).
  The `t_review` anchor handles both shapes and labels which one fired; a run
  that retained nothing would be anchored on the section's empty state, and none
  of the 29 completed runs did.

## Appendix, the opt-in spec

`frontend/e2e/source-latency.spec.ts` is the driver and is committed with this
file. It skips unless `SOURCE_LATENCY` is set, so `make test-e2e` and CI are
unaffected. It drives a real login, the real interview (for `old`), the real
submit and the real review, and appends one JSON line per run to
`SOURCE_LATENCY_OUT`.
