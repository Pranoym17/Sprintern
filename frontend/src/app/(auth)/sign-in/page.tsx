import { Suspense } from "react";
import { AuthForm } from "@/components/auth-form";

export const metadata = { title: "Sign in" };
export default function SignIn() { return <div className="auth-card"><span className="section-kicker">Welcome back</span><h2>Sign in to your alerts</h2><p>Pick up where your internship search left off.</p><Suspense><AuthForm mode="sign-in" /></Suspense></div>; }
