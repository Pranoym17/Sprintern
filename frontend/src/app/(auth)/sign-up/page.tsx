import { Suspense } from "react";
import { AuthForm } from "@/components/auth-form";

export const metadata = { title: "Create account" };
export default function SignUp() { return <div className="auth-card"><span className="section-kicker">Start tracking</span><h2>Create your account</h2><p>Your first focused internship alert is a minute away.</p><Suspense><AuthForm mode="sign-up" /></Suspense></div>; }
