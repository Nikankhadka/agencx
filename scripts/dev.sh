#!/usr/bin/env bash
# Containerized dev stack bootstrap (F-3).
#
# Fixes env files, brings up the whole stack as compose services (db + GoTrue +
# auth-proxy + backend + frontend), runs migrations and optionally seeds the
# demo world. Everything runs detached; `make stop` tears it down.
#
#   scripts/dev.sh           # migrate only (make dev)
#   scripts/dev.sh --seed    # migrate + demo world (make demo)
#
# See docs/agencx/running.md for the walkthrough.
set -euo pipefail

# All paths resolve from the repo root, no matter where the script is invoked.
cd "$(dirname "$0")/.."
ROOT="$PWD"

# --- pretty printing -----------------------------------------------------------
c_reset=$'\033[0m'; c_bold=$'\033[1m'; c_dim=$'\033[2m'; c_green=$'\033[32m'; c_red=$'\033[31m'; c_yellow=$'\033[33m'
say()  { printf '%s\n' "${c_bold}$*${c_reset}"; }
ok()   { printf '%s%s%s\n' "$c_green" "  ✓ $*" "$c_reset"; }
warn() { printf '%s%s%s\n' "$c_yellow" "  ! $*" "$c_reset" >&2; }
die()  { printf '%s%s%s\n' "$c_red" "  ✗ $*" "$c_reset" >&2; exit 1; }

# --- flags ---------------------------------------------------------------------
SEED=0
for arg in "$@"; do
  case "$arg" in
    --seed) SEED=1 ;;
    *) die "unknown argument: $arg (expected --seed)" ;;
  esac
done

# --- 1. preflight --------------------------------------------------------------
say "preflight"
command -v docker >/dev/null || die "docker is not installed. Install Docker Desktop and re-run."
docker info >/dev/null 2>&1 || die "docker daemon is not running. Start Docker Desktop and re-run."
ok "docker ready (the host needs nothing else - everything runs in containers)"

# --- 2. backend/.env -----------------------------------------------------------
say "backend env"
BACKEND_ENV="$ROOT/backend/.env"
if [[ ! -f "$BACKEND_ENV" ]]; then
  cp "$ROOT/.env.example" "$BACKEND_ENV"
  # The migrate runner fails closed on the 'change-me' password placeholder
  # (and on empty/unsafe values); replace it immediately with a generated one.
  generated_pw="wren$(openssl rand -hex 12)"
  awk -v pw="$generated_pw" 'BEGIN{FS=OFS="="} $1=="WREN_APP_DB_PASSWORD"{$2=pw} {print}' \
    "$BACKEND_ENV" > "$BACKEND_ENV.tmp" && mv "$BACKEND_ENV.tmp" "$BACKEND_ENV"
  ok "created backend/.env from .env.example (generated WREN_APP_DB_PASSWORD)"
else
  ok "backend/.env exists (left untouched)"
fi

ensure_env_key() {  # ensure_env_key <file> <key> <value>
  local file="$1" key="$2" val="$3"
  if grep -qE "^${key}=" "$file"; then
    cur="$(grep -E "^${key}=" "$file" | head -1 | cut -d= -f2-)"
    if [[ -z "$cur" ]]; then
      awk -v k="$key" -v v="$val" 'BEGIN{FS=OFS="="} $1==k{$2=v} {print}' "$file" > "$file.tmp" \
        && mv "$file.tmp" "$file"
      ok "set empty $key in $(basename "$file")"
    fi
  else
    printf '%s=%s\n' "$key" "$val" >> "$file"
    ok "added missing $key to $(basename "$file")"
  fi
}

env_val() { grep -E "^$1=" "$2" 2>/dev/null | head -1 | cut -d= -f2- || true; }

jwt_secret="$(env_val SUPABASE_JWT_SECRET "$BACKEND_ENV")"
if [[ -z "$jwt_secret" ]]; then
  jwt_secret="$(openssl rand -hex 32)"
  ensure_env_key "$BACKEND_ENV" SUPABASE_JWT_SECRET "$jwt_secret"
else
  ok "SUPABASE_JWT_SECRET already set in backend/.env"
fi
ensure_env_key "$BACKEND_ENV" SUPABASE_URL "http://localhost:54321"

if [[ "$(env_val WREN_APP_DB_PASSWORD "$BACKEND_ENV")" == "change-me" ]]; then
  warn "WREN_APP_DB_PASSWORD is still 'change-me' in backend/.env - migrations will fail. Set a real value (min 8 chars, no quotes/backslashes/\$)."
fi
if [[ -z "$(env_val LLM_API_KEY "$BACKEND_ENV")" ]]; then
  warn "LLM_API_KEY is empty - live chat will fall back to errors, but seeded transcripts keep the demo working. See .env.example for free-tier options."
fi

# GoTrue's JWT secret is interpolated by compose from the caller's environment.
export SUPABASE_JWT_SECRET="$jwt_secret"
# Also persisted to the compose project env file so EVERY entry point (raw
# `docker compose up`, make targets outside dev.sh) interpolates the same
# secret - otherwise compose sees a config drift and would happily recreate
# auth with an empty one, which GoTrue refuses to boot with. Shell env wins
# over this file when both are present.
ensure_env_key "$ROOT/.env" SUPABASE_JWT_SECRET "$jwt_secret"

# --- 3. infra containers (db + auth + auth-proxy) ------------------------------
"$ROOT/scripts/up-infra.sh"

# --- 4. app containers ---------------------------------------------------------
say "app containers"
docker compose build backend frontend
ok "dev images built"

if [[ -z "$(docker compose run --rm --no-deps -e UV_SYNC_ON_ENTRY=0 backend sh -c '[ -x .venv/bin/python ] && echo yes' 2>/dev/null || true)" ]]; then
  say "installing backend dependencies into their volume (first run pulls torch - this can take a few minutes)"
fi
docker compose run --rm --no-deps backend uv sync --frozen
ok "backend dependencies synced"

say "migrations"
docker compose run --rm backend python -m app.shared.migrate
ok "migrations applied"

if [[ "$SEED" == 1 ]]; then
  say "seeding demo world (first run downloads the embedder model - cached in a volume afterwards)"
  docker compose run --rm backend python -m seeds.seed_demo
  ok "demo world seeded"
else
  warn "no seed - run 'make demo' or 'make seed' for the demo world"
fi

# --- 5. frontend/.env.local (anon key minted inside the container) -------------
say "frontend env"
FE_ENV="$ROOT/frontend/.env.local"
anon_key="$(docker compose run --rm --no-deps backend python -m seeds.supabase_keys anon | tail -1)"
api_url="http://localhost:8000"
supabase_url="http://localhost:54321"

if [[ -f "$FE_ENV" ]]; then
  cp "$FE_ENV" "$FE_ENV.bak"
  ok "backed up existing frontend/.env.local to frontend/.env.local.bak"
fi
set_fe_key() {  # set_fe_key <key> <value>
  local key="$1" val="$2"
  if grep -qE "^${key}=" "$FE_ENV" 2>/dev/null; then
    awk -v k="$key" -v v="$val" 'BEGIN{FS=OFS="="} $1==k{$2=v} {print}' "$FE_ENV" > "$FE_ENV.tmp" \
      && mv "$FE_ENV.tmp" "$FE_ENV"
  else
    printf '%s=%s\n' "$key" "$val" >> "$FE_ENV"
  fi
}
set_fe_key NEXT_PUBLIC_API_URL "$api_url"
set_fe_key NEXT_PUBLIC_SUPABASE_URL "$supabase_url"
set_fe_key NEXT_PUBLIC_SUPABASE_ANON_KEY "$anon_key"
ok "frontend/.env.local ready (API=$api_url, SUPABASE_URL=$supabase_url, anon key minted)"

# --- 6. start app servers ------------------------------------------------------
say "starting servers"
docker compose up -d backend frontend
for _ in $(seq 1 60); do
  curl -fsS http://localhost:8000/health >/dev/null 2>&1 \
    && curl -fsS http://localhost:3000 >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS http://localhost:8000/health >/dev/null 2>&1 || warn "backend not answering on :8000 yet - try 'docker compose logs backend'"
curl -fsS http://localhost:3000 >/dev/null 2>&1 || warn "frontend not answering on :3000 yet - try 'docker compose logs frontend'"

if [[ "$SEED" == 1 ]]; then
  cat <<EOF

${c_green}${c_bold}Agencx demo is up (all containers).${c_reset}

  ${c_bold}Customer chat${c_reset}   http://localhost:3000/bytefix     (no login)
                http://localhost:3000/lumident
  ${c_bold}Tenant console${c_reset}  http://localhost:3000/login       owner@bytefix.dev  / wren-demo
                http://localhost:3000/login       owner@lumident.dev / wren-demo
  ${c_bold}Platform${c_reset}        http://localhost:3000/admin       founder@wren.dev   / wren-demo

  ${c_dim}Logs: docker compose logs -f backend frontend${c_reset}
  ${c_dim}Stop: make stop (data survives) or make clean (full reset)${c_reset}

EOF
else
  cat <<EOF

${c_green}${c_bold}Agencx dev is up (all containers).${c_reset}

  ${c_bold}Frontend${c_reset}   http://localhost:3000
  ${c_bold}Backend${c_reset}    http://localhost:8000/health

  ${c_dim}No demo data seeded - run 'make demo' or 'make seed'.${c_reset}
  ${c_dim}Logs: docker compose logs -f backend frontend${c_reset}
  ${c_dim}Stop: make stop (data survives) or make clean (full reset)${c_reset}

EOF
fi
