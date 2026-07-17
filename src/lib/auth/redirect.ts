const allowedPaths = new Set(["/dashboard", "/matches", "/filters", "/settings"]);

export function safeInternalPath(value: string | null | undefined, fallback = "/dashboard") {
  if (!value || value.includes("\\") || /[\u0000-\u001F\u007F]/.test(value)) return fallback;
  try {
    const decoded = decodeURIComponent(value);
    if (decoded.includes("\\") || decoded.startsWith("//")) return fallback;
    const url = new URL(decoded, "https://sprintern.local");
    if (url.origin !== "https://sprintern.local" || !allowedPaths.has(url.pathname)) return fallback;
    return `${url.pathname}${url.search}${url.hash}`;
  } catch { return fallback; }
}
