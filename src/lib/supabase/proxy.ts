import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { getSupabaseConfig } from "@/lib/env";

const protectedPaths = ["/dashboard", "/matches", "/filters", "/settings"];
const authPaths = ["/sign-in", "/sign-up"];

export async function updateSession(request: NextRequest) {
  let response = NextResponse.next({ request });
  const { url, key } = getSupabaseConfig();
  const supabase = createServerClient(url, key, {
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll: (items) => {
        items.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request });
        items.forEach(({ name, value, options }) => response.cookies.set(name, value, options));
      },
    },
  });
  const { data: { user } } = await supabase.auth.getUser();
  const pathname = request.nextUrl.pathname;
  if (!user && protectedPaths.some((path) => pathname.startsWith(path))) {
    const redirect = request.nextUrl.clone();
    redirect.pathname = "/sign-in";
    redirect.searchParams.set("next", pathname);
    return NextResponse.redirect(redirect);
  }
  if (user && authPaths.includes(pathname)) return NextResponse.redirect(new URL("/dashboard", request.url));
  return response;
}
