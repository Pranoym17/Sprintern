import { PasswordForm } from "@/components/password-form";

export const metadata = { title: "Reset password" };
export default function ForgotPassword() { return <div className="auth-card"><span className="section-kicker">Account recovery</span><h2>Reset your password</h2><p>Enter your account email and we’ll send a secure reset link.</p><PasswordForm mode="request" /></div>; }
