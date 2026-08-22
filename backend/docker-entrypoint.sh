#!/bin/sh
# Dev entrypoint: make sure .venv matches uv.lock before any command runs.
# Quiet when already synced (~1s check); loud output only on real installs so
# `docker compose run --rm backend <cmd>` stays usable as a generic runner.
set -e

if [ "${UV_SYNC_ON_ENTRY:-1}" = "1" ] && [ -f pyproject.toml ]; then
  if ! uv sync --frozen >/tmp/uv-sync.log 2>&1; then
    echo "backend deps failed to install (uv sync --frozen):" >&2
    cat /tmp/uv-sync.log >&2
    exit 1
  fi
fi

exec "$@"
