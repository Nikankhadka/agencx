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
} from "@/lib/auth-session";
import { toast } from "react-hot-toast";

export interface AuthState {
  session: Session | null;
  user: User | null;
  isLoading: boolean;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const supabase = getSupabase();

    supabase.auth.getSession().then(({ data }) => {
      const manual = getManualSession();
      if (data.session) {
        setSession(data.session);
        setCachedSession(data.session);
      } else if (manual) {
        // A login-in-chat (backend-minted) session - synthesize the shape the
        // rest of the app reads (access_token + user.id) so authed routes treat
        // it like a supabase session without supabase-js owning it.
        const synthetic = {
          access_token: manual.access_token,
          expires_at: undefined,
          expires_in: 0,
          token_type: "bearer",
          refresh_token: "",
          user: { id: manual.user_id, email: manual.email } as User,
        } as unknown as Session;
        setSession(synthetic);
        setCachedSession(synthetic);
      } else {
        setSession(null);
        setCachedSession(null);
      }
      setIsLoading(false);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
      setCachedSession(session);
    });

    return () => subscription.unsubscribe();
  }, []);

  const signOut = useCallback(async () => {
    await getSupabase().auth.signOut();
    clearManualSession();
    toast.success("Signed out");
    router.push("/");
  }, [router]);

  return (
    <AuthContext
      value={{ session, user: session?.user ?? null, isLoading, signOut }}
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
