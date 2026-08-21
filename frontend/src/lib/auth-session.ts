import type { Session } from "@supabase/supabase-js";

let _session: Session | null | undefined = undefined;

const MANUAL_SESSION_KEY = "agencx.login-session";

/** A backend-minted login (login-in-chat), not a supabase-js session. */
export interface ManualSession {
  access_token: string;
  user_id: string;
  email: string;
}

export function getCachedSession(): Session | null | undefined {
  return _session;
}

export function setCachedSession(session: Session | null): void {
  _session = session;
}

export function setManualSession(session: ManualSession): void {
  localStorage.setItem(MANUAL_SESSION_KEY, JSON.stringify(session));
}

export function getManualSession(): ManualSession | null {
  const raw = localStorage.getItem(MANUAL_SESSION_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as ManualSession;
    return parsed && parsed.access_token ? parsed : null;
  } catch {
    return null;
  }
}

export function clearManualSession(): void {
  localStorage.removeItem(MANUAL_SESSION_KEY);
}
