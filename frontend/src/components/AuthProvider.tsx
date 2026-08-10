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
import { setCachedSession } from "@/lib/auth-session";

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
      setSession(data.session ?? null);
      setCachedSession(data.session ?? null);
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
