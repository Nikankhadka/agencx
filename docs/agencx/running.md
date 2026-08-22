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
| Customer chat | `http://bytefix.localhost:3000` | none |
| | `http://lumident.localhost:3000` | none |
| Tenant console | `http://app.localhost:3000/login` | `owner@bytefix.dev`, `owner@lumident.dev` |
| Platform | `http://admin.localhost:3000` | `founder@wren.dev` / `wren-demo` |
| Backend API | `http://localhost:8000` | |
| GoTrue (via auth-proxy) | `http://localhost:54321` | |

## Logging in

The tenant console uses login-in-chat: type an email, get a 6-digit code. The
code is issued and sent by **our backend**, not by Supabase - GoTrue only stores
the identity. Where the code lands depends on `EMAIL_PROVIDER` in `backend/.env`:

- `console` (default) - the code is logged by the backend and served by
  `GET http://localhost:8000/api/auth/dev-login-code?email=...` (local only).
- `smtp` with `EMAIL_SMTP_HOST=localhost` - the code goes to Mailpit, which
  `make services` / `make dev` start for you when `backend/.env` opts in. Read
  it at `http://localhost:8025`.

A relay that is down no longer breaks local login: the code is captured before
the send, so delivery failure is a warning and `dev-login-code` still works.
Off local, a failed send is a 502 with real copy, never a 500.

## Environment files

`backend/.env` is the backend's config and is created from the repo-root
`.env.example` by `scripts/dev.sh`. `frontend/.env.local` holds the three
`NEXT_PUBLIC_*` keys and is written by the same script. Neither is committed.
Inside containers, compose overrides the network addresses (`DATABASE_URL`
points at the `db` service, `SUPABASE_URL` at `auth-proxy`, `EMAIL_SMTP_HOST`
at `mailpit`) regardless of what the files say - real env vars beat `.env`
values in pydantic-settings.

## Troubleshooting

**Login returns "Internal Server Error".** Check the backend log for the
`request failed` record carrying the `X-Request-ID` from the response
(`docker compose logs backend`). If `verify-code` is the failing call, GoTrue
is not up - run `make services`.

**Port 3000 or 8000 already in use.** A leftover native dev server (or another
app) holds it. Stop that process; the compose publish then binds cleanly.

**`make seed` fails with `duplicate key ... users_pkey`.** A demo owner email was
used to log in before the demo world was seeded, so login-in-chat minted a
provisional tenant holding that auth user. Drop the provisional tenants
(`delete from tenants where slug like 'owner-%'`) and re-seed.

**Most E2E specs time out.** The stack is not fully up or not seeded. Run
`make dev && make seed` first - the Playwright container drives whatever is
already running, it starts nothing itself.

**Backend container restarts on boot.** Usually a bad `backend/.env`: the
migrate runner fails closed on the `change-me` password placeholder, and empty
required values abort startup off local. `make clean && make demo` regenerates
everything.
