import { Suspense } from "react";
import { AuthForm } from "@/components/auth-form";
import { ServicePausedCard } from "@/components/service-paused-card";
import { PRODUCT_PAUSED } from "@/lib/product-status";

export const metadata = { title: "Create account" };
export default function SignUp() {
  if (PRODUCT_PAUSED) return <ServicePausedCard />;

  return <div className="auth-card"><span className="section-kicker">Start tracking</span><h2>Create your account</h2><p>Your first focused internship alert is a minute away.</p><Suspense><AuthForm mode="sign-up" /></Suspense></div>;
}
