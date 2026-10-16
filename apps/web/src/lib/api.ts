/**
 * Server-side Alpha API client (audit A-C02).
 *
 * Server components and route handlers should import `serverFetch` and
 * never read the public-prefixed key env var. The env var name on
 * the server is FINANCE_TRACKER_API_KEY (no NEXT_PUBLIC_ prefix), so it
 * is never inlined into the client bundle.
 *
 * Client components should call /api/proxy/<path> via the `clientFetch`
 * helper instead — that round-trips through this app's own Next.js
 * route handler, which attaches the key server-side.
 */

const DEFAULT_TIMEOUT_MS = 10_000;

const LOCAL_FALLBACK = "http://localhost:8444";

/**
 * Upstream resolution order (server-side):
 *   1. ALPHA_API_INTERNAL_URL (server runtime, e.g. http://gateway:8444 in compose)
 *   2. NEXT_PUBLIC_API_URL (build-time env, baked into image via compose args)
 *   3. http://localhost:8444 dev-local fallback (last resort, warns)
 *
 * NOTE: browser code must NOT call this — it must use same-origin
 * /api/proxy (clientProxyUrl), which attaches the key server-side.
 */
export function resolveApiBase(): string {
  const fromEnv =
    process.env.ALPHA_API_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_API_URL;
  if (!fromEnv) {
    console.warn(
      "[api] ALPHA_API_INTERNAL_URL/NEXT_PUBLIC_API_URL unset; falling back to localhost:8444 (dev-local only)"
    );
    return LOCAL_FALLBACK;
  }
  return fromEnv;
}

function upstreamBase(): string {
  return resolveApiBase();
}

export interface ServerFetchOptions extends Omit<RequestInit, "signal"> {
  /** Abort signal; if not provided, a 10s timeout is applied. */
  signal?: AbortSignal;
  /** Override the default 10s timeout. */
  timeoutMs?: number;
}

export class ServerFetchError extends Error {
  code: string;
  path: string;
  status?: number;
  constructor(code: string, path: string, message: string, status?: number) {
    super(message);
    this.name = "ServerFetchError";
    this.code = code;
    this.path = path;
    this.status = status;
  }
}

/**
 * Server-side fetch that attaches the FINANCE_TRACKER_API_KEY bearer
 * token. Use this from server components, route handlers, and other
 * server-only code paths. Throws ServerFetchError (never silent null)
 * so misconfiguration surfaces in logs instead of empty UI.
 */
export async function serverFetch<T = unknown>(
  path: string,
  opts: ServerFetchOptions = {}
): Promise<T> {
  const apiKey = process.env.FINANCE_TRACKER_API_KEY;
  if (!apiKey) {
    console.error(
      JSON.stringify({ scope: "serverFetch", reason: "missing-api-key", path })
    );
    throw new ServerFetchError(
      "MISSING_API_KEY",
      path,
      "FINANCE_TRACKER_API_KEY is not configured on the server"
    );
  }
  const base = upstreamBase().replace(/\/$/, "");
  const url = path.startsWith("/") ? `${base}${path}` : `${base}/${path}`;

  const controller = new AbortController();
  const timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  if (opts.signal) {
    opts.signal.addEventListener("abort", () => controller.abort(), { once: true });
  }

  try {
    const res = await fetch(url, {
      ...opts,
      signal: controller.signal,
      headers: {
        ...(opts.headers ?? {}),
        authorization: `Bearer ${apiKey}`,
      },
      cache: opts.cache ?? "no-store",
    });
    if (!res.ok) {
      console.error(
        JSON.stringify({ scope: "serverFetch", reason: "upstream-status", path, status: res.status })
      );
      throw new ServerFetchError("UPSTREAM_STATUS", path, `Upstream ${path} -> ${res.status}`, res.status);
    }
    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof ServerFetchError) throw err;
    if ((err as Error)?.name === "AbortError") {
      console.error(
        JSON.stringify({ scope: "serverFetch", reason: "timeout", path, timeoutMs })
      );
      throw new ServerFetchError("TIMEOUT", path, `${path} timed out after ${timeoutMs}ms`);
    } else {
      console.error(
        JSON.stringify({ scope: "serverFetch", reason: "fetch-failed", path, message: String((err as Error)?.message ?? err) })
      );
      throw new ServerFetchError("FETCH_FAILED", path, `${path} failed: ${(err as Error)?.message ?? err}`);
    }
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Client-side fetch helper. Uses a relative path to /api/proxy/<...>
 * so the FINANCE_TRACKER_API_KEY stays server-side. Browser bundle
 * never sees the real key.
 */
export function clientProxyUrl(path: string): string {
  const trimmed = path.replace(/^\//, "");
  return `/api/proxy/${trimmed}`;
}
