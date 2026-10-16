# Per-call output tokens from cost_logs

The numbers behind the cap choice (`llm_max_tokens_draft` 4096) and the
"cap never bound" finding. `cost_logs` holds one row per LLM call with that
call's `output_tokens`, so it gives true per-call granularity (the run
artifacts only hold per-turn totals).

## Baseline window (captured before the slice-2 runs)

```
$ docker compose exec -T db psql -U postgres -d wren -c "
  select t.slug, count(*) as calls,
    max(cl.output_tokens) as max_out_per_call,
    percentile_disc(0.95) within group (order by cl.output_tokens) as p95_out_per_call,
    percentile_disc(0.50) within group (order by cl.output_tokens) as p50_out_per_call
  from cost_logs cl join tenants t on t.id = cl.tenant_id
  where t.slug in ('bytefix','sababa2','sababa') and cl.created_at >= date_trunc('day', now())
  group by t.slug order by t.slug;"
  slug   | calls | max_out_per_call | p95_out_per_call | p50_out_per_call
---------+-------+------------------+------------------+------------------
 bytefix |    47 |             1803 |             1315 |              234
 sababa  |    48 |             1354 |              867 |              138
 sababa2 |    23 |             1346 |              916 |              400
```

The corpus-wide max is 1803, p95 1315 (bytefix). Captured before the two
slice-2 runs; after `make seed-tenant1` (which wipes bytefix) this exact output
is not reproducible, so it is recorded here.

## Slice-2 window (the last 100 calls at capture time)

The two slice-2 runs account for 66 calls; the remaining ~34 in this window are
later eval calls, so this is the last-100 window, not the runs alone.

```
$ docker compose exec -T db psql -U postgres -d wren -c "
  select max(output_tokens) as max_out_per_call,
    percentile_disc(0.95) within group (order by output_tokens) as p95,
    count(*) as calls
  from (select output_tokens from cost_logs order by created_at desc limit 100) s;"
 max_out_per_call | p95 | calls
------------------+-----+-------
             2003 | 883 |   100
```

The last-100 window's largest call emitted 2003 tokens (below even the first
2048 cap), so the 4096 guard keeps about 2x headroom over the observed max.
