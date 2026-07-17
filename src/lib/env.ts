const browserUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const browserKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export function getSupabaseConfig() {
  if (!browserUrl || !browserKey) {
    throw new Error("Supabase is not configured. Add NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.");
  }
  return { url: browserUrl, key: browserKey };
}

export const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8010";
