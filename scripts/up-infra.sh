#!/usr/bin/env bash
# Bring up the local infra containers: db (Postgres + pgvector), GoTrue auth,
# and the nginx auth-proxy that exposes auth on port 54321. Mailpit (login-in-
# chat's OTP inbox) comes up with them automatically - `auth`'s SMTP settings
# point at it, and it is a compose `depends_on` of `auth` now, not an opt-in
# profile.
#
# Safe to run while the dev servers are up (touches only containers), and
# idempotent. Shared by `make db-full`/`make services` and scripts/dev.sh so
# the container bring-up logic lives in exactly one place.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"

c_reset=$'\033[0m'; c_bold=$'\033[1m'; c_green=$'\033[32m'; c_yellow=$'\033[33m'; c_red=$'\033[31m'
say()  { printf '%s\n' "${c_bold}$*${c_reset}"; }
ok()   { printf '%s%s%s\n' "$c_green" "  ✓ $*" "$c_reset"; }
die()  { printf '%s%s%s\n' "$c_red" "  ✗ $*" "$c_reset" >&2; exit 1; }

say "containers"

# GoTrue refuses to start with an empty JWT secret, and compose interpolates
# it from here into docker-compose.yml.
jwt_secret="$(grep -E '^SUPABASE_JWT_SECRET=' backend/.env 2>/dev/null | head -1 | cut -d= -f2- || true)"
if [[ -z "$jwt_secret" ]]; then
  die "SUPABASE_JWT_SECRET is not set in backend/.env. Run ./scripts/dev.sh once (it generates one), then re-run this script."
fi
export SUPABASE_JWT_SECRET="$jwt_secret"

# db first: GoTrue's first migration assumes the `auth` schema already exists
# (it creates tables as auth.* but does not create the schema), so the schema
# must be present before auth starts. Creating it here is idempotent.
docker compose up -d db
for _ in $(seq 1 30); do
  if docker compose exec -T db pg_isready -U postgres -d wren >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker compose exec -T db pg_isready -U postgres -d wren >/dev/null 2>&1 \
  || die "postgres did not become ready. Try 'docker compose logs db'."
docker compose exec -T db psql -U postgres -d wren -c "create schema if not exists auth;" >/dev/null \
  || die "could not create the auth schema (GoTrue needs it before its first migration)."

docker compose up -d auth auth-proxy

# Wait for the GoTrue health endpoint (through the auth-proxy on 54321).
auth_ready=false
for _ in $(seq 1 40); do
  if curl -fsS http://localhost:54321/health >/dev/null 2>&1; then
    auth_ready=true
    break
  fi
  sleep 1
done
[[ "$auth_ready" == true ]] \
  || die "GoTrue did not become healthy on http://localhost:54321/health. Try 'docker compose logs auth'. (A JWT-secret change against an old volume is harmless - GoTrue signs at request time; if migrations are corrupted, run 'docker compose exec db psql -U postgres -d wren -c \"drop schema if exists auth cascade; create schema auth;\"' then re-run. Note: port 54321 conflicts with a running supabase CLI stack - stop it first.)"
ok "db + GoTrue (auth) + auth-proxy + mailpit up - inbox at http://localhost:8025"