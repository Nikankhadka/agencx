"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * O-2: the sign-up form is retired - login-in-chat (the tenant Chat surface)
 * now handles both login and first-time signup, provisioning the tenant on the
 * first verified email. Anyone landing on the old path is sent there.
 */
export default function SignupPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/");
  }, [router]);
  return null;
}
