# Demo-tenant daily limits

Slice 1 raises the daily ceiling for the three tenants a matrix day runs
(`bytefix`, `sababa2`, `northgate`) so the platform defaults do not end their
chat mid-run. `sababa` is left at the defaults on purpose: it is the unraised
half of the sababa/sababa2 A/B.

The values are seeded, never the app's `DEFAULT_*` constants in
`backend/app/shared/limits.py` (untouched):

```python
# backend/seeds/_helpers.py
DEMO_DAILY_LIMITS = {"daily_cost_usd": 50.0, "daily_tokens": 50_000_000}
```

## Applied to the local dev database

`bytefix` and `sababa2` are direct-DB seeds that write `config.limits` inline:

```
$ make seed-tenant1
$ make seed-sababa2
```

`northgate` is API-provisioned (`seed_tenant2_dental`) and writes its limits
after onboarding confirm. Its seed path is **dead today** on a pre-existing
platform gap, not a latency one: confirm returns
`409 incomplete - missing: ABN; GST registration` because
`seeds/tenant2_inputs/interview-script.md` has no abn/gst stage and
`_check_completeness` requires them. The tenant row is created by signup, so
the limits were applied idempotently with the same helper the seed calls:

```
$ docker compose run --rm -T backend python - <<'PY'
import asyncio
from app.shared import db
from seeds import _helpers


async def main() -> None:
    async with _helpers.seed_pool():
        async with db.tenant_context(None, "platform_admin") as conn:
            tid = await conn.fetchval("select id from tenants where slug = $1", "northgate")
        if tid is None:
            print("northgate tenant absent")
            return
        await _helpers.set_tenant_limits(tenant_id=tid, limits=_helpers.DEMO_DAILY_LIMITS)
        print(f"applied limits to northgate {tid}")


asyncio.run(main())
PY
applied limits to northgate 7824e300-1cd9-4534-b2e6-0f2808bec526
```

## Verification

```
$ docker compose exec -T db psql -U postgres -d wren -c \
  "select t.slug, c.config->'limits' as limits from tenants t \
   join tenant_config c on c.tenant_id=t.id \
   where t.slug in ('bytefix','sababa2','northgate','sababa') order by t.slug;"
   slug      |                       limits
-----------+----------------------------------------------------
 bytefix   | {"daily_tokens": 50000000, "daily_cost_usd": 50.0}
 northgate | {"daily_tokens": 50000000, "daily_cost_usd": 50.0}
 sababa    | 
 sababa2   | {"daily_tokens": 50000000, "daily_cost_usd": 50.0}
```

`northgate` cannot serve a real turn until the ABN/GST confirm gap is fixed, so
it is not yet smoke-verified end to end.
