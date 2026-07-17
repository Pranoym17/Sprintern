const browserUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const browserKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export function getSupabaseConfig() {
  if (!browserUrl || !browserKey) {
    throw new Error("Supabase is not configured. Add NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.");
  }
  return { url: browserUrl, key: browserKey };
}

function getApiUrl() {
  const configured = process.env.NEXT_PUBLIC_API_URL;
  const productionDeployment = process.env.APP_ENV === "production" || process.env.VERCEL_ENV === "production";
  if (!configured && productionDeployment) {
    throw new Error("NEXT_PUBLIC_API_URL is required for a production build.");
  }
  const value = configured ?? "http://127.0.0.1:8010";
  let parsed: URL;
  try { parsed = new URL(value); }
  catch { throw new Error("NEXT_PUBLIC_API_URL must be a valid absolute URL."); }
  if (productionDeployment && parsed.protocol !== "https:") {
    throw new Error("NEXT_PUBLIC_API_URL must use HTTPS in production.");
  }
  return parsed.origin;
}

export const apiUrl = getApiUrl();
