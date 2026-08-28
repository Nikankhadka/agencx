# Running Agencx locally

The one page for getting the stack up, logging in, and knowing which service
each command needs. (The pre-Agencx `docs/archive/DEMO.md` is superseded by this
file and is reference-only.)

## Prerequisites

Docker, running. That is all - Node, Python/uv, Postgres, GoTrue and Mailpit
all live in containers (F-3). Free host ports: 3000, 8000, 5432, 54321.

## One command

```bash
make demo
```

Brings up the whole stack as compose services (db + GoTrue + auth-proxy +
backend + frontend), writes `backend/.env` and `frontend/.env.local`, applies
migrations, seeds the demo world. `make dev` is the same thing without the
seed. Both detach - the stack keeps running until `make stop`.

## Step by step

```bash
make install    # deps into their container volumes (uv sync + npm ci)
make services   # Postgres + pgvector, GoTrue, auth-proxy
make migrate    # forward-only migrations
make seed       # demo world: two tenants, three logins, conversations
make dev        # backend :8000 + frontend :3000 as containers
```

`make db` starts the database **only**. It is not enough to log in - login needs
GoTrue, which is what `make services` adds. Editing source on the host
hot-reloads inside the containers; there are no native servers anymore.

## What each command needs

Targets that can start their own dependencies now do (`docker compose run
backend ...` pulls up the db first). The rest are listed because a long-running
stack cannot be a make prerequisite.

| Command | Needs |
|---|---|
| `make migrate` | db (started for you) |
| `make seed` | db + GoTrue + migrations (all started for you) |
| `make seed-tenant1` | db + migrations (started for you); no auth users, so no GoTrue |
| `make seed-tenant2` | **the stack running** (`make dev`) - it drives the public API over the compose network |
| `make test-e2e` | the seeded stack running (`make dev && make seed`) |
| `make eval` / `make eval-skip-llm` | a seeded db (`make seed-tenant1` is enough) |
| `make test-backend` | db (started for you; the `db`-marked tests use a `wren_test` database) |

## Where things are

| Surface | URL | Login |
|---|---|---|
| Customer chat | `http://localhost:3000/bytefix` | none |
| | `http://localhost:3000/lumident` | none |
| Tenant console | `http://localhost:3000/login` | `owner@bytefix.dev`, `owner@lumident.dev` |
| Platform | `http://localhost:3000/admin` | `founder@wren.dev` / `wren-demo` |
| Backend API | `http://localhost:8000` | |
| GoTrue (via auth-proxy) | `http://localhost:54321` | |

## Logging in

The tenant console uses login-in-chat: type an email, get a 6-digit code.
GoTrue itself issues, mails and verifies the code (`signInWithOtp`/
`verifyOtp`) - the backend is not in this path at all. Locally the mail lands
in **Mailpit**, `make dev`/`make demo` start it automatically (it is a
dependency of the `auth` service, not an opt-in profile): read the code at
`http://localhost:8025`.

## Environment files

`backend/.env` is the backend's config and is created from the repo-root
`.env.example` by `scripts/dev.sh`. `frontend/.env.local` holds the three
`NEXT_PUBLIC_*` keys and is written by the same script. Neither is committed.
Inside containers, compose overrides the network addresses (`DATABASE_URL`
points at the `db` service, `SUPABASE_URL` at `auth-proxy`) regardless of what
the files say - real env vars beat `.env` values in pydantic-settings.

## Troubleshooting

**Login returns "Internal Server Error".** Check the backend log for the
`request failed` record carrying the `X-Request-ID` from the response
(`docker compose logs backend`). If the failure is at the login step itself,
check `docker compose logs auth` instead - GoTrue owns that call now, not the
backend; make sure it (and Mailpit) are up with `make services`.

**Port 3000 or 8000 already in use.** A leftover native dev server (or another
app) holds it. Stop that process; the compose publish then binds cleanly.

**`make seed` fails with `duplicate key ... users_pkey`.** A demo owner email was
used to log in before the demo world was seeded, so login-in-chat minted a
provisional tenant holding that auth user. Drop the provisional tenants
(`delete from tenants where slug like 'owner-%'`) and re-seed.

**Most E2E specs time out.** The stack is not fully up or not seeded. Run
`make dev && make seed` first - the Playwright container drives whatever is
already running, it starts nothing itself.

**A new theme token has no effect** (text renders at 16px, a colour stays the
old one, a radius does not change). Turbopack keeps the set of files it scans
for `@theme` inside `/app/.next`, which is a named volume - so a stale scan
survives `docker restart`, and survives deleting `/app/.next/cache`. Only wiping
the whole directory clears it, which is all `make dev-reset` does (a few
seconds, and nothing but regenerable state). Reach for it before suspecting the
code: if the token still has no effect afterwards, it is the token or the class
name, not the cache - check the value is in `frontend/src/styles/theme.css` and
that the utility namespace actually exists (Tailwind v4 has no `--duration`
namespace, for one, so `duration-fast` silently compiles to nothing). `make
clean` clears the same cache, along with every other volume, the database
included.

**Backend container restarts on boot.** Usually a bad `backend/.env`: the
migrate runner fails closed on the `change-me` password placeholder, and empty
required values abort startup off local. `make clean && make demo` regenerates
everything.
