"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import type { Session, User } from "@supabase/supabase-js";
import { getSupabase } from "@/lib/supabase";
import {
  clearManualSession,
  getManualSession,
  setCachedSession,
  setManualSession,
  type ManualSession,
} from "@/lib/auth-session";
import { toast } from "react-hot-toast";

export interface AuthState {
  session: Session | null;
  user: User | null;
  isLoading: boolean;
  /**
   * Adopt a login-in-chat session (O-2): persist it AND put it into provider
   * state in one step. AuthProvider lives in the root layout and so never
   * remounts on a client navigation - writing localStorage alone would leave
   * `session` null, and the console layout would bounce the owner back out.
   */
  signInWithCode: (manual: ManualSession) => void;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

/**
 * Synthesize the shape the rest of the app reads (access_token + user.id) from
 * a login-in-chat (backend-minted) session, so authed routes treat it like a
 * supabase session without supabase-js owning it.
 */
function syntheticSession(manual: ManualSession): Session {
  return {
    access_token: manual.access_token,
    expires_at: undefined,
    expires_in: 0,
    token_type: "bearer",
    refresh_token: "",
    user: { id: manual.user_id, email: manual.email } as User,
  } as unknown as Session;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const supabase = getSupabase();

    /**
     * Resolve the effective session: a supabase-js session wins, otherwise the
     * login-in-chat (backend-minted) one, otherwise signed out.
     *
     * Both entry points must go through this. supabase-js emits an
     * INITIAL_SESSION event carrying `null` whenever it holds no session of its
     * own, so an onAuthStateChange handler that trusted its argument would wipe
     * a login-in-chat session moments after it was stored and bounce the owner
     * straight back to /login (O-2).
     */
    function resolve(supabaseSession: Session | null): void {
      if (supabaseSession) {
        setSession(supabaseSession);
        setCachedSession(supabaseSession);
        return;
      }
      const manual = getManualSession();
      if (!manual) {
        setSession(null);
        setCachedSession(null);
        return;
      }
      const synthetic = syntheticSession(manual);
      setSession(synthetic);
      setCachedSession(synthetic);
    }

    supabase.auth.getSession().then(({ data }) => {
      resolve(data.session);
      setIsLoading(false);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      resolve(session);
    });

    return () => subscription.unsubscribe();
  }, []);

  const signInWithCode = useCallback((manual: ManualSession) => {
    setManualSession(manual);
    const synthetic = syntheticSession(manual);
    setSession(synthetic);
    setCachedSession(synthetic);
  }, []);

  const signOut = useCallback(async () => {
    await getSupabase().auth.signOut();
    clearManualSession();
    toast.success("Signed out");
    router.push("/");
  }, [router]);

  return (
    <AuthContext
      value={{
        session,
        user: session?.user ?? null,
        isLoading,
        signInWithCode,
        signOut,
      }}
    >
      {children}
    </AuthContext>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
