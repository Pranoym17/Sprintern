import { createBrowserClient } from "@supabase/ssr";
import { getSupabaseConfig } from "@/lib/env";

let client: ReturnType<typeof createBrowserClient> | undefined;

export function createClient() {
  const { url, key } = getSupabaseConfig();
  client ??= createBrowserClient(url, key);
  return client;
}
