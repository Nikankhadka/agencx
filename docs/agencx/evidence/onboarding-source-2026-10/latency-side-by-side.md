# Onboarding source: old and new latency side by side (ticket 29)

Measured on 2026-10-27 from the backend container in the local docker stack
(`docker compose run --rm --no-deps backend ...`) against the tree at `e926422`,
the tip of the 29 + 30 stack, with `scripts/source_timing_probe.py` added in
the same working tree. Each run measures two shapes of the same source turn:
the site fetch (`crawl_site`) and the processing that loads it (the readable
sections pass, the offering extraction pass and the profile read), with
`legacy` meaning the pre-ticket crawl (`legacy_discovery=True`, 3 concurrent
reads, 30s deadline) followed by those same shipped functions composed
serially, and `new` meaning the shipped crawl followed by the shipped
concurrent draft and profile read. **The legacy shape is not an old checkout:
it is a serial composition of the same shipped functions**, which is the only
honest way to compare the two in one tree and isolates exactly the composition
the ticket changed. `--provider stub` replaces the model with a fixed sleep per
call type (structure 1200ms, offerings 900ms, profile 700ms) so the serial sum
against the longest path is provable with no model noise; `--provider real`
uses the configured chain. Shapes run legacy first, then new, inside every run
so provider drift hits both.

Environment, honestly: local docker compose stack, wall-clock measurements
only, the configured provider chain is Google `gemini-3.5-flash-lite` (free
tier) as primary with OpenRouter `deepseek/deepseek-v4.1-flash` (paid) as the
fallback and Z.ai as the failover. The fixture real run logged two internal
"llm rate-limited; retrying" lines and both calls then succeeded; no row in
these tables is a 429. One grounds legacy run is a 45s per-call timeout and is
reported as such. No p50 or p95 target is claimed: two URLs and three runs per
shape cannot support one.

## Table 1, fetch

`crawl_site` wall time, median of three runs for fixture and grounds (the same
session as Tables 3 and 4), and the single `crawl_probe` run for nandos, which
needs no model. Coverage is the new crawl's characters as a percentage of the
legacy crawl's, and the overlap column is `crawl_probe`'s priced-name coverage
where it ran.

| Label | URL | Runs | Pages (legacy / new) | Chars (legacy / new) | Coverage | Legacy ms | New ms | Delta ms | Delta % |
|---|---|---|---|---|---|---|---|---|---|
| fixture | `http://frontend:3000/fixtures/example-business.html` | 3 | 5 / 5 | 3,664 / 3,664 | 100.0% | 669 | 310 | -359 | -53.7% |
| grounds | `https://www.thegrounds.com.au/` | 3 | 6 / 4 | 11,484 / 11,439 | 99.6% | 4,523 | 2,178 | -2,345 | -51.8% |
| nandos | `https://www.nandos.com.au/` | 1 | 9 / 9 | 11,484 / 7,657 | 66.7% | 1,771 | 1,701 | -70 | -4.0% |

The same-session `crawl_probe` run, which reads the URL twice back to back,
agrees on the direction and gives the fetched text at that moment:

| Label | Pages (legacy / new) | Chars (legacy / new) | Coverage | Legacy ms | New ms | Delta ms | Delta % | Priced names |
|---|---|---|---|---|---|---|---|---|
| fixture | 5 / 5 | 3,664 / 3,664 | 100.0% | 814 | 255 | -559 | -68.7% | 6/6 |
| grounds | 6 / 4 | 11,450 / 11,439 | 99.9% | 6,840 | 2,242 | -4,598 | -67.2% | 0/0 |
| nandos | 9 / 9 | 11,484 / 7,657 | 66.7% | 1,771 | 1,701 | -70 | -4.0% | 2/3 |

The grounds text differs by a few characters between runs because the site is
live and its navigation is not identical on every fetch; the page counts do not
change. The stub fixture's first legacy crawl carries a cold-start outlier
(3,787ms); the fetch medians above come from the real-provider session and are
unaffected.

## Table 2, processing (stub)

Same text, same functions, no model noise. Expected composition is
`structure + offerings + profile` serially against `max(structure, offerings)`
with the profile read overlapping the draft. Processing total is the measured
turn time minus its own crawl; the per-pass numbers are the probe's own timing
of each `extract` call.

| Label | Legacy composition | New composition | Legacy expected ms | New expected ms | Legacy measured ms | New measured ms | Delta ms | Delta % |
|---|---|---|---|---|---|---|---|---|
| fixture | 1,202 + 902 + 703 | max(1,203, 902) with 703 alongside | 2,806 | 1,203 | 2,810 | 1,204 | -1,607 | -57.2% |
| grounds | 1,202 + 901 + 702 | max(1,202, 901) with 703 alongside | 2,805 | 1,202 | 2,812 | 1,206 | -1,606 | -57.1% |

Measured medians sit 1 to 7ms above the arithmetic, which is gather and task
overhead. The composition is what the ticket changed: the legacy shape pays
the sum of all three passes, the new shape pays the slowest of the two draft
passes while the profile read finishes under it.

## Table 3, processing (real provider)

The same processing half, on real calls. Processing total is the turn time minus
its crawl. The median is taken only over runs where every call completed.

| Label | Runs completed (legacy / new) | Legacy measured ms | New measured ms | Delta ms | Delta % | Failure markers |
|---|---|---|---|---|---|---|
| fixture | 3/3 / 3/3 | 6,839 | 2,655 | -4,184 | -61.2% | none |
| grounds | 2/3 / 3/3 | 6,117 | 2,846 | -3,271 | -53.5% | legacy run 1: `timeout` - the structure call took 31.5s and the offerings call then hit the 45s per-call cap; no completed value is substituted for it |

The fixture medians hide one new-path run where the profile call alone took
6.8s while the draft finished in 2.8s; that run's processing was 6,838ms. The
median is the honest summary of the three, and the raw appendix keeps the
outlier visible. The grounds legacy median is the mean of two completed runs
(5,129ms and 7,106ms), not a three-run median.

## Table 4, end to end

Crawl plus processing, per URL, the same medians as Tables 1 and 2/3.

| Label | Provider | Legacy ms | New ms | Delta ms | Delta % | Runs completed (legacy / new) |
|---|---|---|---|---|---|---|
| fixture | stub | 3,503 | 1,435 | -2,069 | -59.0% | 3/3 / 3/3 |
| grounds | stub | 8,244 | 4,309 | -3,935 | -47.7% | 3/3 / 3/3 |
| fixture | real | 7,508 | 2,928 | -4,579 | -61.0% | 3/3 / 3/3 |
| grounds | real | 10,030 | 5,024 | -5,005 | -49.9% | 2/3 / 3/3 |

`www.nandos.com.au` has no end-to-end row: it needs no model to be read, it was
measured by `crawl_probe` only, and no real-provider processing was run against
it.

## Verdict

"Equal" here means within 10%, or within the observed run-to-run spread when
that is wider. The spreads measured: stub processing is tight (fixture legacy
2,809-2,813ms and new 1,203-1,206ms; grounds legacy 2,811-2,813ms and new
1,205-1,207ms, under 1%); fetch is the noisy half (fixture legacy 640-694ms,
new 221-323ms; grounds legacy 3,302-5,573ms, new 1,765-3,448ms; nandos is one
run at 1,771 against 1,701ms); real totals span 6,503-7,844ms legacy and
2,876-7,161ms new on fixture (the 7,161 is the profile outlier), and
8,431-11,629ms legacy against 4,632-5,524ms new on grounds, with one legacy
run timing out at 84,449ms.

- **fixture: faster.** Fetch 53.7% faster, processing 57.2% faster on the stub
  proof and 61.2% on the real provider, end to end 59.0% (stub) and 61.0%
  (real). Coverage is identical, 3,664 characters on both. The one new-path
  run at 7.2s is a slow profile call, not a composition regression: its draft
  still finished in 2.8s.
- **grounds: faster.** Fetch 51.8% faster, processing 53.5% faster on the real
  provider, end to end 49.9%. Coverage is 99.6% (11,439 against 11,484
  characters), and the new path completed all three runs while one legacy run
  lost 84s to a per-call timeout.
- **nandos: equal on fetch, worse on coverage.** 1,701ms against 1,771ms
  (-4.0%) is inside the spread this directory's earlier three-run session
  recorded for nandos (new 842-2,215ms, legacy 966-2,828ms), so no slowdown is
  claimed. Coverage is 66.7% of the legacy text and 2 of 3 priced names, which
  is the known miss already recorded in this directory's README, not a new
  regression introduced by this measurement.
- **overall: the latency work is a success on the two URLs measured end to
  end.** Every completed comparison is faster, the processing gain is exactly
  the composition the stub proves, and the crawl gain comes without losing
  material on the fixture or the grounds. The caveat is evidence thickness: the
  real-provider processing medians rest on three fixture pairs and two legacy
  grounds pairs, and model latency on this chain is noisy enough that a single
  run can erase the gain for that run. The structural claim does not depend on
  those medians; the stub does.

## Appendix: raw runs

One line per run per shape. Times in milliseconds. `stub` and `real` are the
provider modes; `crawl` is the fetch, `struct`/`offer`/`profile` are the sum of
that call type's calls, `draft` is the document draft, `total` is the whole
shape.

```
fixture, stub
run 1 legacy  crawl 3787 pages 5 chars 3664 struct 1202 offer  902 profile  703 draft 2107 total  6597 ok
run 1 new     crawl  227 pages 5 chars 3664 struct 1205 offer  902 profile  704 draft 1207 total  1433 ok
run 2 legacy  crawl  690 pages 5 chars 3664 struct 1203 offer  905 profile  703 draft 2110 total  3503 ok
run 2 new     crawl  232 pages 5 chars 3664 struct 1201 offer  901 profile  702 draft 1203 total  1435 ok
run 3 legacy  crawl  422 pages 5 chars 3664 struct 1202 offer  902 profile  704 draft 2105 total  3231 ok
run 3 new     crawl  272 pages 5 chars 3664 struct 1203 offer  903 profile  703 draft 1204 total  1476 ok

grounds, stub
run 1 legacy  crawl 5431 pages 6 chars 11484 struct 1202 offer  901 profile  702 draft 2109 total  8244 ok
run 1 new     crawl 1876 pages 4 chars 11439 struct 1201 offer  901 profile  703 draft 1205 total  3081 ok
run 2 legacy  crawl 6971 pages 6 chars 11484 struct 1202 offer  902 profile  703 draft 2108 total  9782 ok
run 2 new     crawl 3103 pages 4 chars 11439 struct 1202 offer  902 profile  703 draft 1206 total  4308 ok
run 3 legacy  crawl 4717 pages 6 chars 11484 struct 1202 offer  901 profile  702 draft 2109 total  7528 ok
run 3 new     crawl 3902 pages 4 chars 11439 struct 1202 offer  901 profile  703 draft 1206 total  5109 ok

fixture, real
run 1 legacy  crawl  640 pages 5 chars 3664 struct 3260 offer 2234 profile 1703 draft 5501 total  7844 ok
run 1 new     crawl  310 pages 5 chars 3664 struct 2613 offer 2293 profile 2181 draft 2618 total  2928 ok
run 2 legacy  crawl  694 pages 5 chars 3664 struct 2796 offer 1446 profile 1562 draft 4248 total  6503 ok
run 2 new     crawl  221 pages 5 chars 3664 struct 2651 offer 1814 profile 2020 draft 2654 total  2876 ok
run 3 legacy  crawl  669 pages 5 chars 3664 struct 3721 offer 1762 profile 1350 draft 5488 total  7508 ok
run 3 new     crawl  323 pages 5 chars 3664 struct 2818 offer 2134 profile 6838 draft 2822 total  7161 ok

grounds, real
run 1 legacy  crawl 5573 pages 6 chars 11484 struct 31530 offer 45004 profile 2322 draft 76553 total 84449 timeout
run 1 new     crawl 1765 pages 4 chars 11439 struct  2858 offer  2134 profile 1689 draft  2867 total  4632 ok
run 2 legacy  crawl 3302 pages 6 chars 11484 struct  1950 offer  1646 profile 1520 draft  3608 total  8431 ok
run 2 new     crawl 2178 pages 4 chars 11439 struct  2838 offer  1820 profile 1747 draft  2845 total  5024 ok
run 3 legacy  crawl 4523 pages 6 chars 11484 struct  2314 offer  2337 profile 2446 draft  4658 total 11629 ok
run 3 new     crawl 3448 pages 4 chars 11439 struct  1876 offer  2066 profile 1590 draft  2076 total  5524 ok
```

`crawl_probe` from the same session:

```
fixture legacy  pages 5 chars 3664   wall   814 timeout False skipped budget=0,duplicate_content=0,empty=0
fixture new     pages 5 chars 3664   wall   255 timeout False skipped budget=0,duplicate_content=0,empty=0 overlap 6/6
grounds legacy  pages 6 chars 11450  wall  6840 timeout False skipped budget=3,duplicate_content=1,duplicate_path=3,junk=7,other_site=29,page_cap=49
grounds new     pages 4 chars 11439  wall  2242 timeout False skipped budget=0,duplicate_content=1,duplicate_path=3,junk=4,other_site=29,page_cap=30 overlap 0/0
nandos  legacy  pages 9 chars 11484  wall  1771 timeout False skipped budget=1,junk=31,other_site=3,page_cap=294
nandos  new     pages 9 chars 7657   wall  1701 timeout False skipped budget=1,junk=31,other_site=3,page_cap=295 overlap 2/3
```

## Reproduction

```
docker compose run --rm --no-deps backend python -m scripts.source_timing_probe \
    --url http://frontend:3000/fixtures/example-business.html --label fixture \
    --runs 3 --provider stub
docker compose run --rm --no-deps backend python -m scripts.source_timing_probe \
    --url https://www.thegrounds.com.au/ --label grounds --runs 3 --provider stub
docker compose run --rm --no-deps backend python -m scripts.source_timing_probe \
    --url http://frontend:3000/fixtures/example-business.html --label fixture \
    --runs 3 --provider real
docker compose run --rm --no-deps backend python -m scripts.source_timing_probe \
    --url https://www.thegrounds.com.au/ --label grounds --runs 3 --provider real
docker compose run --rm --no-deps backend python -m scripts.crawl_probe \
    --url https://www.nandos.com.au/ --label nandos
```

The probe also accepts `--json <path>`; the raw payloads behind these tables
were written to `backend/var/timing/` (gitignored scratch). The fixture needs
the compose stack running; the probe warms the site once outside the
measurement because `next dev` compiles each route on its first request.
