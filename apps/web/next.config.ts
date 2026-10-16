import type { NextConfig } from "next";

// BUG-1 fix: Guard against missing NEXT_PUBLIC_SITE_URL in production.
// Without this, OG tags, robots.txt, sitemap.xml, and JSON-LD would render
// with an empty/wrong host. The canonical host comes from env (set per
// deployment in hosting/Docker/compose); there is no hardcoded domain here.
if (process.env.NODE_ENV === "production" && !process.env.NEXT_PUBLIC_SITE_URL) {
  throw new Error(
    "[SEO] NEXT_PUBLIC_SITE_URL must be set in production. " +
    "Add it to your hosting environment variables (Vercel, Railway, Docker, etc.)."
  );
}

// connect-src stays narrow: self + the configured API host only.
// default-src is untouched ('self').
function apiOriginForCsp(): string {
  const raw =
    process.env.NEXT_PUBLIC_API_URL ||
    process.env.ALPHA_API_INTERNAL_URL ||
    "http://localhost:8444";
  try {
    return new URL(raw).origin;
  } catch {
    return "http://localhost:8444";
  }
}

const securityHeaders = [
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=()",
  },
  { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: https:",
      "font-src 'self' data:",
      "object-src 'none'",
      "base-uri 'self'",
      "frame-ancestors 'none'",
      `connect-src 'self' ${apiOriginForCsp()}`,
    ].join("; "),
  },
];

const nextConfig: NextConfig = {
  /* config options here */
  // Required for Docker production builds (enables `node server.js` standalone runner)
  output: "standalone",
  async headers() {
    return [{ source: "/(.*)", headers: securityHeaders }];
  },
};

export default nextConfig;
