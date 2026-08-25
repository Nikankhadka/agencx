from __future__ import annotations

from functools import lru_cache
from urllib.parse import quote, urlsplit, urlunsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, sourced from the environment / local .env.

    Field names map to upper-case env vars (``database_url`` <- ``DATABASE_URL``).
    Only names appear in ``.env.example``; real values live in local ``.env`` and,
    in production, a secrets manager.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Deployment environment: 'local' | 'ci' | 'production'. Anything other than
    # 'local'/'ci' is treated as a real deployment by the startup guard, which
    # then refuses placeholder/empty secrets (app/core/startup.py).
    environment: str = "local"

    # Log level for the structured JSON logger (app/observability/logging.py).
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/wren"
    wren_app_db_password: str = "change-me"

    # Supabase auth (wired in T-004)
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""
    # Presented to GoTrue's Admin API and to Storage. Projects created after
    # Supabase moved to asymmetric (ES256) session signing have no symmetric JWT
    # secret to mint a service token from, so the real key is the only way in.
    supabase_service_role_key: str = ""

    # Login-in-chat email delivery (O-2): 'console' (log the code - the local
    # demo path) or 'smtp' (a standard relay). Adding a vendor (e.g. Resend) is
    # a new provider class in app/services/email.py, never a schema change.
    email_provider: str = "console"
    email_smtp_host: str = ""
    email_smtp_port: int = 587
    email_smtp_from: str = ""

    # Chat LLM provider: 'azure' | 'openai_compat' | 'zai'. 'openai_compat'
    # speaks the OpenAI wire format against any base URL (OpenRouter, Groq,
    # Ollama, ...), so swapping hosted vendors is a config change, never a code
    # change. 'zai' is Z.ai's GLM Flash line: the same wire format but with the
    # two Z.ai quirks handled (json_object extract mode, thinking disabled).
    llm_provider: str = "azure"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""

    # Optional fallback chat provider: when a base URL and model are set, every
    # LLM call fails over to this provider after the primary's internal retries
    # are exhausted (transient 429s, unusable upstream bodies, malformed
    # structured output). Empty base URL = failover disabled, the app uses the
    # primary provider alone. llm_fallback_provider selects the vendor class:
    # 'zai' (default - Z.ai's free GLM Flash models, json_object extract mode)
    # or 'openai_compat' (any other OpenAI-compatible endpoint, e.g. OpenRouter
    # when the primary is Z.ai). The fallback is always OpenAI-compatible.
    llm_fallback_provider: str = "zai"
    llm_fallback_base_url: str = ""
    llm_fallback_api_key: str = ""
    llm_fallback_model: str = ""

    # P-1 third leg: the independent failover tier (D15's OpenRouter gemma).
    # Primary and fallback are usually the two fastest free tiers, which is
    # exactly why they are the two most likely to be rate-limited on the same
    # afternoon; the third leg exists to be somebody else's infrastructure. Same
    # rules as the fallback: model + key set = enabled, empty = the chain is two
    # legs long.
    llm_failover_provider: str = "openai_compat"
    llm_failover_base_url: str = ""
    llm_failover_api_key: str = ""
    llm_failover_model: str = ""

    # P-2: how long the primary leg gets to produce a first token before the
    # next leg starts racing it (PRD section 9's 4s promise). Configurable
    # because it is a product decision about how long a customer waits before
    # the system hedges, not a property of any provider.
    llm_ttft_budget_s: float = 4.0

    # P-1: the standing budget for live model testing, in whole dollars (D16).
    # The cost dashboard warns at 80% of it. Free tiers report zero cost, so
    # this only ever bites once a paid key is in play - which is the moment it
    # matters.
    llm_monthly_budget_usd: float = 10.0

    # Output caps, 0 = uncapped (the default, and the behavior before these
    # existed).
    #
    # DO NOT set these without checking whether the configured model is a
    # REASONING model. Reasoning models (the current default,
    # nvidia/nemotron-3-super-*, and any o1/R1-class model) spend their output
    # budget on hidden thinking tokens BEFORE emitting an answer, and those
    # count against max_tokens. Measured here: a 256-token cap on a structured
    # extract was fully consumed by ~300 reasoning tokens, so the model emitted
    # no JSON at all and every turn died with LengthFinishReasonError. A cap
    # that looks generous for the visible answer can still be far too small.
    #
    # They are kept as knobs because on a NON-reasoning model, capping the
    # draft is a real latency win (the draft was 23s of a measured 37s turn,
    # scaling with emitted prose). Set them per-model, never blindly.
    llm_max_tokens_draft: int = 0
    llm_max_tokens_extract: int = 0

    # T-041: tool calling mode. 'auto' (the default) uses native function calling
    # when the model supports it; 'on' forces native; 'off' forces the emulated
    # extract()-based fallback path, for free models that lack native tool support
    # (per the standing $0-deploy principle).
    llm_tool_calling: str = "auto"

    # Azure OpenAI (used when llm_provider='azure' and/or embedder='azure')
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_chat_deployment: str = "gpt-4o-mini"
    azure_openai_embed_deployment: str = "text-embedding-3-small"

    # Embedder: 'local' | 'azure' | 'google' - independent of llm_provider on
    # purpose (local embeddings + hosted chat is the default $0 stack).
    # embedding_dim must match knowledge_chunks.embedding's vector(N) (migration
    # 0010); pointing at a model with a different dimension needs a migration +
    # re-ingest. 'google' is the deployed default (B-4): the production image
    # ships without sentence-transformers, so 'local' is not available there.
    # It reuses llm_api_key rather than taking a Google key of its own.
    embedder: str = "local"
    local_embed_model: str = "BAAI/bge-small-en-v1.5"
    google_embed_model: str = "text-embedding-004"
    embedding_dim: int = 384

    # Reranker (T-009): 'cohere' | 'local'
    reranker: str = "local"
    cohere_api_key: str = ""

    # Uploads root (T-007). Local filesystem path, used only when
    # ``uploads_bucket`` is empty - see app/shared/storage.py.
    uploads_dir: str = "var/uploads"
    # Supabase Storage bucket for raw uploads. Set in any deployment whose disk
    # does not survive between requests (Vercel container services): the upload
    # request writes the file and a later save request reads it back to chunk.
    uploads_bucket: str = ""

    # O-4 whole-corpus fast path: the total prompt budget, in tokens, a tenant's
    # corpus is allowed to occupy before retrieval scoring is worth its latency.
    # A corpus that fits is handed to the model whole (no embed, no rerank); one
    # that does not runs the hybrid pipeline unchanged. This is a measured token
    # count, never a branch on business size - see app/services/retrieval.py.
    corpus_fast_path_max_tokens: int = 7500

    # Observability (T-030): Langfuse tracing is opt-in - empty keys mean the
    # tracer no-ops, so the free-first stack runs with zero external tracing.
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    @property
    def app_database_url(self) -> str:
        """The same database, but as the un-privileged ``wren_app`` role the API uses."""
        parts = urlsplit(self.database_url)
        netloc = f"wren_app:{quote(self.wren_app_db_password, safe='')}@{parts.hostname}"
        if parts.port:
            netloc = f"{netloc}:{parts.port}"
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


@lru_cache
def get_settings() -> Settings:
    return Settings()
