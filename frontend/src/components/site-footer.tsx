import Link from "next/link";
import { Brand } from "@/components/brand";

const links = [
  { href: "/privacy", label: "Privacy" },
  { href: "/terms", label: "Terms" },
  { href: "/data-sources", label: "Job data & accuracy" },
  { href: "/contact", label: "Contact" },
];

export function SiteFooter({ compact = false }: { compact?: boolean }) {
  return <footer className={compact ? "site-footer site-footer--compact" : "site-footer"}>
    {!compact && <Brand />}
    <p>Internship alerts without the refresh loop.</p>
    <nav aria-label="Trust and support">{links.map((link) => <Link href={link.href} key={link.href}>{link.label}</Link>)}</nav>
  </footer>;
}
