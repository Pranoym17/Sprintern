import { PasswordForm } from "@/components/password-form";

export const metadata = { title: "Choose new password" };
export default function ResetPassword() { return <div className="auth-card"><span className="section-kicker">Secure your account</span><h2>Choose a new password</h2><p>Use at least eight characters and avoid reusing an old password.</p><PasswordForm mode="reset" /></div>; }
