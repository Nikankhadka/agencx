-- 0002_roles.sql - the two application roles.
-- The runner substitutes the WREN_APP_DB_PASSWORD placeholder (dollar-brace syntax,
-- spelled out below only inside the create-role literal so the secret appears exactly
-- once in the executed statement text) from the environment before executing. The
-- runner validates the value fail-closed: no quotes, backslashes, or dollar signs.

-- Roles are cluster-global (not per-database), so guard creation: a second database
-- in the same cluster (e.g. the test database) reuses the roles created by the first.
-- The runner still guarantees each file runs once per database via schema_migrations.
do $$ begin
  -- The FastAPI backend's only DB identity: LOGIN, no BYPASSRLS, CRUD via grants.
  if not exists (select 1 from pg_roles where rolname = 'wren_app') then
    create role wren_app login password '${WREN_APP_DB_PASSWORD}';
  end if;
  -- Owns resolve_tenant_slug only: the single audited RLS bypass in the system.
  if not exists (select 1 from pg_roles where rolname = 'wren_resolver') then
    create role wren_resolver nologin bypassrls;
  end if;
end $$;

-- Giving a function away requires membership in the role receiving it, and
-- PG16 made that membership explicit rather than implied by having created the
-- role. A true superuser has it regardless; a managed Postgres does not, so on
-- Supabase 0003's `alter function ... owner to wren_resolver` failed with
-- "must be able to SET ROLE \"wren_resolver\"" before any of this schema
-- existed. Harmless where the migrating user is already a superuser.
grant wren_resolver to current_user;

grant usage on schema public to wren_app;
alter default privileges in schema public
  grant select, insert, update, delete on tables to wren_app;
-- USAGE alone is not enough for wren_resolver to *own* resolve_tenant_slug:
-- Postgres requires a new owner to hold CREATE on the function's schema, and
-- only waives that for superusers. Local migrations run as one and never saw
-- it; Supabase's `postgres` is not a superuser, so 0003 failed with
-- "permission denied for schema public". The role stays NOLOGIN and owns
-- exactly the one audited function.
grant usage, create on schema public to wren_resolver;
