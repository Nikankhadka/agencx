"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { apiFetch, ApiError } from "@/lib/api";
import { getSupabase } from "@/lib/supabase";
import { useAuth } from "@/components/AuthProvider";
import { toast } from "react-hot-toast";

/**
 * T-033: platform-owner login (frontend.md 7.3). Mirrors the tenant-admin
 * login flow, but probes GET /api/platform/ping and redirects straight into
 * the Tenants page on success - there is only one thing to do on this
 * surface. No signup link: platform admins are bootstrapped directly in the
 * database (database.md section 3), there is no self-serve path.
 */
export default function PlatformLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const { session, isLoading } = useAuth();

  useEffect(() => {
    if (isLoading || !session) return;
    let active = true;
    apiFetch<{ ok: boolean }>("/api/platform/ping")
      .then(() => {
        if (active) router.replace("/");
      })
      .catch(() => {
        /* signed in but not a platform admin - stay on the login form */
      });
    return () => { active = false; };
  }, [isLoading, session, router]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const { error: authError } = await getSupabase().auth.signInWithPassword({
        email,
        password,
      });
      if (authError) {
        setError(authError.message);
        toast.error(authError.message);
        return;
      }
      await apiFetch<{ ok: boolean }>("/api/platform/ping");
      toast.success("Logged in successfully");
      router.replace("/");
    } catch (err) {
      const message =
        err instanceof ApiError && err.status === 403
          ? "This account is not a platform admin."
          : err instanceof ApiError
            ? err.detail
            : "Something went wrong. Please try again.";
      setError(message);
      toast.error(message);
    } finally {
      setBusy(false);
    }
  }

  if (isLoading) {
    return (
      <main className="flex min-h-dvh items-center justify-center p-4 sm:p-8">
        <div aria-busy="true" className="w-full max-w-sm rounded-lg border border-border bg-surface p-6 shadow-1" />
      </main>
    );
  }

  return (
    <main className="flex min-h-dvh items-center justify-center p-4 sm:p-8">
      <div className="w-full max-w-sm rounded-lg border border-border bg-surface p-6 shadow-1">
        <h1 className="text-title-2 font-semibold">Log in</h1>
        <p className="mt-1 text-body-sm text-text-secondary">Wren platform</p>
        <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4" noValidate>
          <Input
            label="Email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Input
            label="Password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={error ?? undefined}
          />
          <Button type="submit" loading={busy}>
            Log in
          </Button>
        </form>
      </div>
    </main>
  );
}
