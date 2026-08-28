-- 0022_drop_auth_codes.sql - auth migration: login-in-chat moves to GoTrue OTP.
--
-- The backend no longer issues or verifies its own 6-digit codes (see
-- 0017_auth_codes.sql) - GoTrue's signInWithOtp/verifyOtp does both, and the
-- session it hands back replaces the backend-minted HS256 token. Nothing else
-- referenced this table (it was RLS-scoped to the service role only), so it
-- drops whole: RLS policies and the index go with it.
drop table auth_codes;
