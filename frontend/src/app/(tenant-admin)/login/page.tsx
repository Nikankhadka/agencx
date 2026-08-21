"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ChatBubble } from "@/components/ui/ChatBubble";
import { CodeInput } from "@/components/ui/CodeInput";
import { CommandPill } from "@/components/ui/CommandPill";
import { apiFetch, ApiError } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

interface VerifyResponse {
  access_token: string;
  user_id: string;
  tenant_id: string;
}

/**
 * O-2: login-in-chat. The owner authenticates inside the conversation - type an
 * email, receive a 6-digit code, type it back - instead of a sign-up form. The
 * agent's first message is rendered up front (no welcome screen).
 */
export default function LoginPage() {
  const router = useRouter();
  const { session, isLoading, signInWithCode } = useAuth();

  const [phase, setPhase] = useState<"email" | "code">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [resendReady, setResendReady] = useState(false);
  const resendTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!isLoading && session) {
      router.replace("/onboarding");
    }
  }, [isLoading, session, router]);

  useEffect(() => {
    return () => {
      if (resendTimer.current) clearTimeout(resendTimer.current);
    };
  }, []);

  async function submitEmail(value: string) {
    const trimmed = value.trim().toLowerCase();
    if (!EMAIL_RE.test(trimmed) || busy) return;
    setEmail(trimmed);
    setStatus(null);
    setBusy(true);
    try {
      await apiFetch("/api/auth/login-code", {
        method: "POST",
        body: JSON.stringify({ email: trimmed }),
      });
      setPhase("code");
      setResendReady(false);
      resendTimer.current = setTimeout(() => setResendReady(true), 30_000);
    } catch {
      // calm - no red chrome; the pill simply stays put
      setStatus("Something went wrong - try again.");
    } finally {
      setBusy(false);
    }
  }

  async function submitCode(value: string) {
    if (busy) return;
    setCode(value);
    setStatus(null);
    setBusy(true);
    try {
      const res = await apiFetch<VerifyResponse>("/api/auth/verify-code", {
        method: "POST",
        body: JSON.stringify({ email, code: value }),
      });
      signInWithCode({
        access_token: res.access_token,
        user_id: res.user_id,
        email,
      });
      router.replace("/onboarding");
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : "Something went wrong.";
      setStatus(detail);
      setCode("");
      setBusy(false);
    }
  }

  function handleWrongEmail() {
    setPhase("email");
    setEmail("");
    setCode("");
    setStatus(null);
  }

  if (isLoading || session) return null;

  return (
    <main className="flex min-h-dvh items-center justify-center p-4 sm:p-8">
      <div className="flex w-full max-w-md flex-col gap-4">
        <div className="flex flex-col gap-3">
          <ChatBubble role="assistant">
            Hi, I&apos;ll get you set up. What&apos;s your email?
          </ChatBubble>

          {phase === "code" ? (
            <ChatBubble role="system">
              Code sent to <span className="font-medium text-text">{email}</span>
            </ChatBubble>
          ) : null}
        </div>

        {phase === "email" ? (
          <CommandPill
            value={email}
            onChange={setEmail}
            onSubmit={submitEmail}
            placeholder="you@example.com"
            busy={busy}
            canSubmit={EMAIL_RE.test(email.trim())}
          />
        ) : (
          <div className="flex flex-col gap-3">
            <CodeInput value={code} onChange={setCode} onComplete={submitCode} disabled={busy} />
            <div className="flex items-center justify-between text-footnote">
              <button
                type="button"
                onClick={handleWrongEmail}
                className="font-medium text-accent hover:text-accent-hover"
              >
                Wrong email?
              </button>
              <button
                type="button"
                onClick={() => void submitEmail(email)}
                disabled={!resendReady || busy}
                className="font-medium text-text-secondary disabled:opacity-50"
              >
                Didn&apos;t get it? Resend
              </button>
            </div>
          </div>
        )}

        <p className="h-4 text-footnote text-text-secondary" aria-live="polite">
          {status ?? ""}
        </p>
      </div>
    </main>
  );
}
