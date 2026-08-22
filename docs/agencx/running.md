# Running Agencx locally

The one page for getting the stack up, logging in, and knowing which service
each command needs. (The pre-Agencx `docs/archive/DEMO.md` is superseded by this
file and is reference-only.)

## Prerequisites

Node 22+, [uv](https://docs.astral.sh/uv/), Docker (running), and free ports
3000, 8000, 5432, 54321.

## One command

```bash
make demo
```

Brings up the database and GoTrue, writes `backend/.env` and
`frontend/.env.local`, applies migrations, seeds the demo world, and starts both
dev servers. `make dev` is the same thing without the seed and with reload.

## Step by step

```bash
make install    # frontend (npm ci) + backend (uv sync)
make db-full    # Postgres + pgvector, GoTrue, auth-proxy
make migrate    # forward-only migrations
make seed       # demo world: two tenants, three logins, conversations
make dev-backend    # :8000   (one terminal)
make dev-frontend   # :3000   (another)
```

`make db` starts the database **only**. It is not enough to log in - login needs
GoTrue, which is what `make db-full` adds.

## What each command needs

Targets that can start their own dependencies now do (`make seed` brings up
GoTrue and runs migrations first). The rest are listed here because a
long-running server cannot be a make prerequisite.

| Command | Needs |
|---|---|
| `make migrate` | db (started for you) |
| `make seed` | db + GoTrue + migrations (all started for you) |
| `make seed-tenant1` | db + migrations (started for you); no auth users, so no GoTrue |
| `make seed-tenant2` | db + GoTrue **+ a running backend** - it drives the public API |
| `make test-e2e` | a seeded db + **a running backend**; Playwright starts only the frontend |
| `make eval` / `make eval-skip-llm` | a seeded db (`make seed-tenant1` is enough) |
| `make test-backend` | db (the `db`-marked tests use a `wren_test` database) |

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
  `make db-full` / `make dev` start for you. Read it at `http://localhost:8025`.

A relay that is down no longer breaks local login: the code is captured before
the send, so delivery failure is a warning and `dev-login-code` still works.
Off local, a failed send is a 502 with real copy, never a 500.

## Environment files

`backend/.env` is the backend's config and is created from the repo-root
`.env.example` by `scripts/demo.sh`. `frontend/.env.local` holds the three
`NEXT_PUBLIC_*` keys and is written by the same script. Neither is committed.

## Troubleshooting

**Login returns "Internal Server Error".** Check the backend log for the
`request failed` record carrying the `X-Request-ID` from the response. If
`verify-code` is the failing call, GoTrue is not up - run `make db-full`.

**`make demo` says port 5432 is in use.** Something other than this project's db
container holds it. `docker compose ps -q db` is what the preflight checks.

**`make seed` fails with `duplicate key ... users_pkey`.** A demo owner email was
used to log in before the demo world was seeded, so login-in-chat minted a
provisional tenant holding that auth user. Drop the provisional tenants
(`delete from tenants where slug like 'owner-%'`) and re-seed.

**Most E2E specs time out.** The backend is not running, or the demo world is not
seeded. Playwright starts the frontend only.
