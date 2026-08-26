# B-4: production image for the Vercel `backend` service (vercel.json), and the
# `test` stage CI runs the suite in. Multi-stage: uv resolves/builds the venv in
# one layer, the runtime layer only ships the venv + app source, keeping the
# final image lean.
#
# The image is LEAN by construction: sentence-transformers/torch (the local
# EMBEDDER/RERANKER dev default, ~100MB+) lives in pyproject's `local-ml`
# dependency group, installed by default everywhere EXCEPT here
# (--no-group local-ml below), which is why production binds EMBEDDER/RERANKER
# to hosted providers - launching this image with EMBEDDER=local or
# RERANKER=local fails at first use with ModuleNotFoundError, by design.

FROM python:3.12.14-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.5.31 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev --no-group local-ml

COPY . .
RUN uv sync --frozen --no-dev --no-group local-ml

# The stage CI runs pytest in, so the suite executes against the same image
# lineage that ships rather than against a separately-installed host toolchain.
# It adds only the `dev` group on top of builder - still no local-ml, because
# every test that touches the local embedder/reranker stubs the model rather
# than loading weights (tests/test_rerank_normalization.py).
FROM builder AS test

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

RUN uv sync --frozen --no-group local-ml

CMD ["pytest"]

FROM python:3.12.14-slim AS runtime

RUN useradd --create-home --uid 1000 wren
WORKDIR /app

COPY --from=builder --chown=wren:wren /app /app

# The `test` stage needs tests/ in the build context, so .dockerignore cannot
# exclude them and the builder carries them. Nothing in production runs them.
RUN rm -rf /app/tests

# PORT is the contract every container host in play sets for us, and it is
# deliberately NOT baked in here: the host decides. Vercel injects it per service
# (the frontend was observed on 80), which is why deploy.md step 2 says to leave
# PORT unset - a project-level value would apply to BOTH services and send one of
# them to the wrong socket. Cloud Run injects 8080, and local compose leaves it
# unset so the 8000 fallback in CMD applies. Baking ENV PORT would make the
# container listen somewhere the host is not sending traffic.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER wren

EXPOSE 8000

# The venv interpreter is named absolutely rather than resolved through PATH.
# A container host is free to inject its own environment over the image's, and
# Vercel does: the first deploy died with `sh: 1: exec: uvicorn: not found`
# even though ENV PATH above puts the venv first and the binary is present.
# ${PORT:-8000} still needs a shell, so this stays `sh -c` rather than exec form.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD /app/.venv/bin/python -c "import os,urllib.request; urllib.request.urlopen('http://localhost:%s/health' % os.environ.get('PORT','8000'))" || exit 1

CMD ["sh", "-c", "exec /app/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
