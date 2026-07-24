"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { ArrowRight, LoaderCircle, LogIn } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { safeInternalPath } from "@/lib/auth/redirect";

export function AuthForm({ mode }: { mode: "sign-in" | "sign-up" }) {
  const router = useRouter();
  const params = useSearchParams();
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(params.get("error") === "confirmation" ? "That confirmation link could not be completed. Please try again." : params.get("reason") === "session-expired" ? "Your session expired. Sign in again to continue." : null);
  const isSignUp = mode === "sign-up";

  async function continueWithGoogle() {
    setPending(true); setMessage(null);
    const { error } = await createClient().auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent("/onboarding")}` },
    });
    if (error) { setMessage("Google sign-in could not be started. Please try again."); setPending(false); }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPending(true); setMessage(null);
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "").trim();
    const password = String(form.get("password") ?? "");
    const supabase = createClient();
    if (isSignUp) {
      const callback = `${window.location.origin}/auth/callback?next=${encodeURIComponent("/onboarding")}`;
      const { data, error } = await supabase.auth.signUp({ email, password, options: { emailRedirectTo: callback } });
      setPending(false);
      if (error) return setMessage(error.message);
      if (!data.session) return setMessage("Check your inbox to confirm your account, then sign in.");
    } else {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) { setPending(false); return setMessage(error.message); }
    }
    router.replace(isSignUp ? "/onboarding" : safeInternalPath(params.get("next")));
    router.refresh();
  }

  return <form className="auth-form" onSubmit={submit} aria-busy={pending}>
    <button className="button oauth-button" type="button" disabled={pending} onClick={continueWithGoogle}><LogIn size={19} />Continue with Google</button>
    <div className="auth-divider"><span>or use email</span></div>
    <div className="field"><label htmlFor="email">Email address</label><input id="email" name="email" type="email" autoComplete="email" required placeholder="you@example.com" /></div>
    <div className="field"><div className="field-label-row"><label htmlFor="password">Password</label>{!isSignUp && <Link href="/forgot-password">Forgot password?</Link>}</div><input id="password" name="password" type="password" minLength={8} autoComplete={isSignUp ? "new-password" : "current-password"} required /><span className="field__help">At least 8 characters</span></div>
    {message && <p className="form-message" role="status">{message}</p>}
    <button className="button button--dark button--full" disabled={pending}>{pending ? <LoaderCircle className="spin" size={18} /> : null}{isSignUp ? "Create account" : "Sign in"}<ArrowRight size={18} /></button>
    <p className="auth-switch">{isSignUp ? "Already tracking?" : "New to Sprintern?"} <Link href={isSignUp ? "/sign-in" : "/sign-up"}>{isSignUp ? "Sign in" : "Create an account"}</Link></p>
  </form>;
}
