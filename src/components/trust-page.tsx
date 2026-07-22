import Link from "next/link";
import type { ReactNode } from "react";
import { Brand } from "@/components/brand";
import { SiteFooter } from "@/components/site-footer";

export function TrustPage({ eyebrow, title, intro, children }: { eyebrow: string; title: string; intro: string; children: ReactNode }) {
  return <div className="trust-page"><a className="skip-link" href="#trust-content">Skip to content</a><header className="trust-header"><Brand /><Link href="/">Back to home</Link></header><main id="trust-content" className="trust-content"><span className="section-kicker">{eyebrow}</span><h1>{title}</h1><p className="trust-intro">{intro}</p><div className="trust-sections">{children}</div></main><SiteFooter /></div>;
}

export function TrustSection({ title, children }: { title: string; children: ReactNode }) { return <section><h2>{title}</h2>{children}</section>; }
