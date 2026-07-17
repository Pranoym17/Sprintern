"use client";

import { FormEvent, useState } from "react";
import { ArrowRight, LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";

import { createClient } from "@/lib/supabase/client";

export function PasswordForm({ mode }: { mode: "request" | "reset" }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPending(true); setMessage("");
    const data = new FormData(event.currentTarget);
    if (mode === "request") {
      const email = String(data.get("email") ?? "").trim();
      const redirectTo = `${window.location.origin}/auth/callback?next=${encodeURIComponent("/reset-password")}`;
      const { error } = await createClient().auth.resetPasswordForEmail(email, { redirectTo });
      setPending(false);
      setMessage(error ? "The reset email could not be sent. Please try again." : "If that account exists, a password-reset link is on its way.");
      return;
    }
    const password = String(data.get("password") ?? "");
    const confirmation = String(data.get("confirmation") ?? "");
    if (password !== confirmation) { setMessage("The passwords do not match."); setPending(false); return; }
    const { error } = await createClient().auth.updateUser({ password });
    if (error) { setMessage("Your password could not be updated. Request a new reset link and try again."); setPending(false); return; }
    router.replace("/dashboard"); router.refresh();
  }

  return <form className="auth-form" onSubmit={submit} aria-busy={pending}>
    {mode === "request" ? <div className="field"><label htmlFor="recovery-email">Email address</label><input id="recovery-email" name="email" type="email" autoComplete="email" required placeholder="you@example.com" /></div> : <><div className="field"><label htmlFor="new-password">New password</label><input id="new-password" name="password" type="password" minLength={8} autoComplete="new-password" required /><span className="field__help">At least 8 characters</span></div><div className="field"><label htmlFor="password-confirmation">Confirm password</label><input id="password-confirmation" name="confirmation" type="password" minLength={8} autoComplete="new-password" required /></div></>}
    {message && <p className="form-message" role="status">{message}</p>}
    <button className="button button--dark button--full" disabled={pending}>{pending && <LoaderCircle className="spin" size={18} />}{mode === "request" ? "Send reset link" : "Update password"}<ArrowRight size={18} /></button>
  </form>;
}
