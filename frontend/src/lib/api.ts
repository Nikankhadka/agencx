import { getSupabase } from "./supabase";
import type { components } from "./api-types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
    public readonly code = "request_failed",
    public readonly requestId?: string,
    public readonly errors: components["schemas"]["ProblemError"][] = []
  ) {
    super(`${status}: ${detail}`);
    this.name = "ApiError";
  }
}

/**
 * Builds request headers for backend calls: attaches the current Supabase
 * session's access token as a bearer header. FormData sets its own multipart
 * Content-Type (with the boundary the browser generates) - forcing
 * application/json here would break uploads.
 *
 * `getSession()` is the one source of truth for the token (no separate
 * client-side cache to keep in sync with it): it reads the cookie
 * `getSupabase()` writes and refreshes it when needed, the same session
 * `src/proxy.ts` rotates server-side on navigation.
 */
async function getAuthHeaders(init: RequestInit): Promise<Headers> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const { data } = await getSupabase().auth.getSession();
  if (data.session) {
    headers.set("Authorization", `Bearer ${data.session.access_token}`);
  }
  return headers;
}

/**
 * Turns a failed backend response into an ApiError carrying the backend's
 * `detail` string so pages can show it verbatim.
 */
async function throwApiError(res: Response): Promise<never> {
  let detail = "The request could not be completed.";
  let code = "request_failed";
  let requestId: string | undefined;
  let errors: components["schemas"]["ProblemError"][] = [];
  try {
    const body = (await res.json()) as Partial<components["schemas"]["ProblemDetails"]>;
    if (typeof body.type === "string" && typeof body.detail === "string") {
      detail = body.detail;
      code = typeof body.code === "string" ? body.code : code;
      requestId = typeof body.request_id === "string" ? body.request_id : undefined;
      errors = Array.isArray(body.errors) ? body.errors : [];
    }
  } catch {
    // non-JSON error body; keep statusText
  }
  throw new ApiError(res.status, detail, code, requestId, errors);
}

/**
 * Backend fetch wrapper (T-004): attaches the current Supabase session's
 * access token as a bearer header. Throws ApiError with the backend's
 * `detail` string on non-2xx so pages can show it verbatim.
 */
export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { ...init, headers: await getAuthHeaders(init) });
  if (!res.ok) await throwApiError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/**
 * Backend fetch wrapper for streaming (SSE) responses: same auth and error
 * handling as apiFetch, but returns the raw Response so the caller can read
 * the stream body incrementally.
 */
export async function apiFetchStream(path: string, init: RequestInit = {}): Promise<Response> {
  const res = await fetch(`${API_URL}${path}`, { ...init, headers: await getAuthHeaders(init) });
  if (!res.ok) await throwApiError(res);
  return res;
}
