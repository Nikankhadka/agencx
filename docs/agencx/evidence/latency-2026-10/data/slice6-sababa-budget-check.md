# Slice 6 - sababa daily-budget pre-check

Same query as `sababa-budget-check.md`, run before the slice-6 matrix. Sababa is
deliberately left at the platform defaults (2,000,000 tokens and $5 per UTC
day), so it is the one corpus tenant that can run out mid-matrix.

```
$ docker compose exec -T db psql -U postgres -d wren -c "
  select t.slug,
    coalesce(sum(cl.input_tokens + cl.output_tokens), 0) as tokens_today,
    count(*) as calls_today,
    (select c.config->'limits' from tenant_config c where c.tenant_id = t.id) as limits
  from tenants t
  left join cost_logs cl on cl.tenant_id = t.id and cl.created_at >= date_trunc('day', now())
  where t.slug in ('sababa','sababa2','bytefix')
  group by t.id, t.slug order by t.slug;"
```

Output at the slice-6 pre-check (2026-10-20, UTC day):

```
  slug   | tokens_today | calls_today |                       limits
---------+--------------+-------------+----------------------------------------------------
 bytefix |        72457 |          13 | {"daily_tokens": 50000000, "daily_cost_usd": 50.0}
 sababa  |        80883 |          18 |
 sababa2 |       171146 |          15 | {"daily_tokens": 50000000, "daily_cost_usd": 50.0}
```

Remaining for sababa today: 2,000,000 - 80,883 = **1,919,117 tokens**.

Planned sababa turns: 5 (slice-6 run 1) + 5 (slice-6 run 2) = 10 turns. At the
observed ~15k tokens per hybrid turn that is about 150k tokens, roughly 8% of
the remaining budget.

**Verdict: PROCEED.** The remaining sababa budget covers the planned turns with
wide margin, so no matrix turn should be cut off by the daily token cap.
