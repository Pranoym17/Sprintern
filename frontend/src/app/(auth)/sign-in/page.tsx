import { Suspense } from "react";
import { AuthForm } from "@/components/auth-form";
import { ServicePausedCard } from "@/components/service-paused-card";
import { PRODUCT_PAUSED } from "@/lib/product-status";

export const metadata = { title: "Sign in" };
export default function SignIn() {
  if (PRODUCT_PAUSED) return <ServicePausedCard />;

  return <div className="auth-card"><span className="section-kicker">Welcome back</span><h2>Sign in to your alerts</h2><p>Pick up where your internship search left off.</p><Suspense><AuthForm mode="sign-in" /></Suspense></div>;
}
