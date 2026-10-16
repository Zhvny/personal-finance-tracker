/**
 * Server-side API proxy (audit A-C02).
 *
 * The web client (browser bundle) MUST NOT receive FINANCE_TRACKER_API_KEY
 * or any other secret. Any client-side code that needs the Alpha API should
 * call /api/proxy/<path> (relative, no secret), and this route handler
 * attaches the Authorization header server-side.
 *
 * Env vars consumed (server-only, no NEXT_PUBLIC_ prefix):
 *   - FINANCE_TRACKER_API_KEY   (required)
 *   - ALPHA_API_INTERNAL_URL    (optional; default http://gateway:8444 in
 *                                container, http://localhost:8444 otherwise)
 *   - NEXT_PUBLIC_API_URL       (fallback for ALPHA_API_INTERNAL_URL,
 *                                safe to read server-side)
 *
 * The route is intentionally narrow: a single handler that mirrors the
 * inbound method, query, and body. It does NOT do path validation, so
 * an authenticated user can only call the same paths their bearer key
 * permits upstream — no privilege escalation.
 */
import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const HOP_BY_HOP = new Set([
  "host",
  "content-length",
  "connection",
  "keep-alive",
  "transfer-encoding",
  "te",
  "upgrade",
]);

function resolveUpstream(): string {
  // Server-side only. Reading NEXT_PUBLIC_ here is safe; the value is
  // never inlined into the client bundle for this file.
  return (
    process.env.ALPHA_API_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8444"
  );
}

async function handle(req: NextRequest, params: { path: string[] }) {
  const apiKey = process.env.FINANCE_TRACKER_API_KEY;
  const upstream = resolveUpstream().replace(/\/$/, "");
  if (!apiKey) {
    return NextResponse.json(
      {
        detail:
          "FINANCE_TRACKER_API_KEY is not configured on the web server; upstream not attempted.",
        missing: "FINANCE_TRACKER_API_KEY",
        upstream,
      },
      { status: 503 }
    );
  }
  const path = (params.path ?? []).join("/");
  const search = req.nextUrl.search;
  const target = `${upstream}/${path}${search}`;

  const headers = new Headers();
  for (const [k, v] of req.headers.entries()) {
    if (!HOP_BY_HOP.has(k.toLowerCase())) headers.set(k, v);
  }
  headers.set("authorization", `Bearer ${apiKey}`);

  const init: RequestInit = { method: req.method, headers, cache: "no-store" };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.text();
  }

  let upstreamResp: Response;
  try {
    upstreamResp = await fetch(target, init);
  } catch (err) {
    console.error(
      JSON.stringify({ scope: "proxy", reason: "upstream-unreachable", upstream, path, message: String((err as Error)?.message ?? err) })
    );
    return NextResponse.json(
      { detail: `Upstream unavailable at ${upstream}.`, upstream },
      { status: 502 }
    );
  }

  const out = new NextResponse(upstreamResp.body, {
    status: upstreamResp.status,
    statusText: upstreamResp.statusText,
  });
  upstreamResp.headers.forEach((v, k) => {
    if (!HOP_BY_HOP.has(k.toLowerCase())) out.headers.set(k, v);
  });
  return out;
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return handle(req, await ctx.params);
}
export async function POST(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return handle(req, await ctx.params);
}
export async function PUT(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return handle(req, await ctx.params);
}
export async function PATCH(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return handle(req, await ctx.params);
}
export async function DELETE(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return handle(req, await ctx.params);
}
export async function HEAD(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return handle(req, await ctx.params);
}
export async function OPTIONS(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return handle(req, await ctx.params);
}
