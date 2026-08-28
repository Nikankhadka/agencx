import { describe, expect, it } from "vitest";
import { authCookieOptions } from "./auth-cookie";

describe("authCookieOptions", () => {
  it("marks production session cookies Secure and SameSite Lax", () => {
    expect(authCookieOptions(true)).toEqual({ secure: true, sameSite: "lax" });
  });

  it("keeps local HTTP development usable", () => {
    expect(authCookieOptions(false)).toEqual({ secure: false, sameSite: "lax" });
  });
});
