/** Shared cookie policy for browser sign-in and server-side session refresh. */
export function authCookieOptions(isProduction = process.env.NODE_ENV === "production") {
  return { secure: isProduction, sameSite: "lax" as const };
}
