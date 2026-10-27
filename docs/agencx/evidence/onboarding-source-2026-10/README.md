# Onboarding source: crawl and processing speed (ticket 29)

Measured on 2026-10-27 from the backend container (`docker compose run --rm
--no-deps backend ...`) with the compose stack running.

This run is the post-fix measurement: the table below replaces the slice D
numbers after the crawl learned to stop at the budget, to fall back to the
sitemap on a thin result, and to rank that fallback by path depth.

## What changed after slice D

- The crawl consumes page reads as they complete (`asyncio.wait` with
  `FIRST_COMPLETED`) and assembles the settled prefix in selection order. It
  stops as soon as the page budget or the character budget is full and cancels
  the remaining reads. A read cancelled at the budget is never fetched, never
  recorded as a failure, and never recorded as a skip reason.
- The sitemap fallback also fires on a thin result. Tiered pages (priority 1-6)
  are read first; if discovery hit the page cap and either no offerings-tier
  page was read or the gathered text is below 60% of `max_chars`, the sitemaps
  are fetched, merged with the nav/body selection, re-ranked, and the unread
  pages are read within the remaining page slots.
- The fallback's ranking is depth-first for sitemap-sourced candidates: fewer
  path segments beat the tier, so a deep `/menu-item/*` page cannot outrank a
  shallow page of the same site. At most two sitemap pages are selected from
  one first path segment, and untiered nav/body pages still come last. A flat
  sitemap has one depth, so its tier order is unchanged.
- A site whose nav/body selection fits under the page cap never fetches a
  sitemap: the frontier was already exhausted, so a sitemap could only add
  latency. This is what keeps the fixture fast.
- `legacy_discovery=True` still reproduces the pre-ticket selection and now also
  keeps the pre-ticket wait-for-every-read shape, so the probe compares the new
  crawl with the old one rather than with itself.
- Unchanged: 10 pages, 11,500 characters, per-page caps (4,000 / 6,000), six
  concurrent reads, 10s deadline.

## Probe

```
docker compose run --rm --no-deps backend python -m scripts.crawl_probe \
    --url <url> --label <label>
```

Each run reads the URL twice: legacy selection (`legacy_discovery=True`,
`concurrency=3`, `timeout_s=30`) and the shipped defaults (`concurrency=6`,
`timeout_s=10`). "Overlap" is coverage of the legacy crawl's priced material:
the offering name before the price on each price-bearing line of the legacy
text, counted when that name survives in the new text.

The fixture is served by `next dev`; the probe warms the URL once before
measuring so the dev server's first-request compile is not charged to whichever
mode ran first.

## Post-fix rows (three runs per URL, median ms)

| Label | URL | Pages (legacy / new) | Chars (legacy / new) | Legacy ms | New ms | Skip reasons, new | Overlap |
|---|---|---|---|---|---|---|---|
| fixture | `http://frontend:3000/fixtures/example-business.html` | 5 / 5 | 3,664 / 3,664 | 461 | 145 | none | 6/6 |
| python | `https://www.python.org/` | 6 / 6 | 11,468 / 11,468 | 967 | 1,350 | budget=1, other_site=64, page_cap=53 | 0/0 |
| grounds | `https://www.thegrounds.com.au/` | 6 / 4 | 11,443 / 11,440 | 6,281 | 1,882 | budget=1, duplicate_content=1, duplicate_path=3, junk=4, other_site=29, page_cap=30 | 0/0 |
| nandos | `https://www.nandos.com.au/` | 9 / 9 | 11,484 / 7,657 | 1,575 | 1,676 | budget=1, junk=31, other_site=3, page_cap=295 | 2/3 |

Every row: `timed_out=False` in both modes.

Raw runs, in order (ms):

| Label | Legacy | New |
|---|---|---|
| fixture | 20,089, 316, 461 | 4,302, 144, 145 |
| python | 967, 674, 1,366 | 476, 1,537, 1,350 |
| grounds | 3,885, 6,281, 6,332 | 1,882, 2,696, 1,768 |
| nandos | 1,575, 966, 2,828 | 2,215, 842, 1,676 |

The fixture's first run carries the dev server's cold compile (the warm-up
request did not settle it); the medians are unaffected.

The slice D table, before these two changes, for comparison:

| Label | Pages (legacy / new) | Chars (legacy / new) | Legacy ms | New ms | Overlap |
|---|---|---|---|---|---|
| fixture | 5 / 5 | 3,664 / 3,664 | 330 | 176 | 6/6 |
| python | 6 / 6 | 11,468 / 11,468 | 1,455 | 3,344 | 0/0 |
| grounds | 6 / 4 | 11,442 / 11,499 | 8,109 | 3,147 | 0/0 |
| nandos | 9 / 7 | 11,484 / 5,464 | 925 | 1,319 | 2/3 |

## What this shows

- Fixture: 145 ms against 461 ms, same five pages and the same 3,664
  characters. The crawl fills the character budget and the page cap gate keeps
  a small site from paying for a sitemap round trip.
- python.org: the same six pages and the same 11,468 characters, so coverage
  is unchanged. This run's medians put the new crawl 383 ms slower (1,350
  against 967) on a 476-1,537 ms spread; the same page set is read, and the
  previous table had the new run faster. Network noise, not a selection
  change.
- The Grounds: 1,882 ms against 6,281 ms, with 11,440 characters against
  11,443 (99.97% of legacy).
- `www.nandos.com.au` improves but misses the bar: 7,657 characters against
  11,484, which is 66.7% of the legacy text (was 6,531 and 57%). The
  depth-first fallback stops `/menu-item/*` from taking every slot and keeps
  the two offering names (2/3), but the site's shallow pages are mostly
  chrome: `/menu` reads 220 characters, and four of the seven sitemap pages
  read were under 500. The rich legacy pages are either deeper
  (`/our-story/*`) or untiered at depth 1 (`/rate-your-nandos`). The cap and
  the depth order cannot reach 90% on this site without a second mechanism,
  so the number stands here.
- Speed on nandos is close to the legacy shape: 1,676 ms against 1,575 ms
  (three-run medians), inside the site's own spread.

## Not measured

- The validation matrix names stylesbyjaimy, Sydney Dental Care, Phone Clinic,
  the Sabbaba 96-item menu and a multi-location clinic. `stylesbyjaimy.com`,
  `www.stylesbyjaimy.com` and `www.sabbaba.com.au` did not resolve from the
  container, and the other sites were not identified by a URL I could verify.
  No row is claimed for them.
- The matrix's "3-page fixture" does not exist in the repo; the only fixture
  site is the four-page `example-business` set.
- No guarantee is claimed for the fallback model, large PDFs or slow sites.

## Processing-half verification

```
docker compose run --rm backend pytest tests/test_onboarding_api.py -q -k timing
# 1 passed (the source turn emits one "onboarding source timing" record
# carrying crawl_ms, draft_ms, structure_ms, offerings_ms, profile_ms,
# reply_ms, total_ms)
docker compose run --rm backend pytest -q
# 1624 passed
```
