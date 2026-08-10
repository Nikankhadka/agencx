import type { Session } from "@supabase/supabase-js";

let _session: Session | null | undefined = undefined;

export function getCachedSession(): Session | null | undefined {
  return _session;
}

export function setCachedSession(session: Session | null): void {
  _session = session;
}
