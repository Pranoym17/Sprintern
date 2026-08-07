import type { NextConfig } from "next";

function allowedOrigin(value: string | undefined) {
  if (!value) return null;
  try { return new URL(value).origin; } catch { return null; }
}

const connectSources = [
  "'self'",
  allowedOrigin(process.env.NEXT_PUBLIC_API_URL),
  allowedOrigin(process.env.NEXT_PUBLIC_SUPABASE_URL),
  process.env.NEXT_PUBLIC_SUPABASE_URL?.startsWith("https://")
    ? `wss://${new URL(process.env.NEXT_PUBLIC_SUPABASE_URL).host}`
    : null,
].filter(Boolean).join(" ");

const contentSecurityPolicy = [
  "default-src 'self'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  "object-src 'none'",
  `script-src 'self' 'unsafe-inline'${process.env.NODE_ENV === "development" ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src ${connectSources}`,
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: contentSecurityPolicy },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
  { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
];

const nextConfig: NextConfig = {
  // Vercel already traces and packages Next applications. Standalone output is
  // only required by our Docker image; enabling it on Vercel can make its
  // builder look for Docker-specific trace artifacts that Next does not emit.
  ...(process.env.SPRINTERN_DOCKER_BUILD === "true" ? { output: "standalone" } : {}),
  async headers() { return [{ source: "/(.*)", headers: securityHeaders }]; },
};

export default nextConfig;
