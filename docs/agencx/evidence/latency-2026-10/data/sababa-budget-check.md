# Sababa daily-budget pre-check (before the matrix)

Sababa was deliberately left at the platform defaults (2,000,000 tokens and $5
per UTC day), so it is the one corpus tenant that can run out mid-matrix. This
check is whether its remaining budget covers every planned turn.

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
  slug    | tokens_today | calls_today |                       limits
----------+--------------+-------------+----------------------------------------------------
 bytefix  |       136151 |          25 | {"daily_tokens": 50000000, "daily_cost_usd": 50.0}
 sababa   |        11046 |           3 |
 sababa2  |            0 |           1 | {"daily_tokens": 50000000, "daily_cost_usd": 50.0}
```

Remaining for sababa today: 2,000,000 - 11,046 = **1,988,954 tokens**.

Planned sababa turns: 5 (noise run 1, also the deepseek matrix row) + 5 (noise
run 2) + 5 (matrix, inclusionai/ling-3.0-flash) = 15 turns. Observed cost today
is about 3.7k tokens per call over a partial hybrid turn; at roughly 15k tokens
per turn, 15 turns is about 225k tokens, about 11% of the remaining budget.

**Verdict: PROCEED.** The remaining sababa budget covers the planned turns with
wide margin, so no matrix turn should be cut off by the daily token cap.
