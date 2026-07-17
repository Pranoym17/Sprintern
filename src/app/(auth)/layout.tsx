import Link from "next/link";
import { Brand } from "@/components/brand";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return <main className="auth-layout auth-layout--minimal"><header className="auth-minimal-header"><Brand /><Link className="auth-back" href="/">← Back to home</Link></header><section className="auth-content">{children}</section><p className="auth-trust">Focused alerts. Original application links. No job-board noise.</p></main>;
}
