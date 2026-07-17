import Link from "next/link";
import { BellRing, Filter, Radio } from "lucide-react";
import { Brand } from "@/components/brand";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return <main className="auth-layout"><section className="auth-panel"><Brand /><div className="auth-panel__content"><span className="section-kicker">Your internship signal</span><h1>Less refreshing.<br /><em>More applying.</em></h1><p>Build one focused alert and let Sprintern watch the Summer 2027 board for you.</p><ul><li><Radio /> Checks every 15 minutes</li><li><Filter /> Matches your own criteria</li><li><BellRing /> Sends instant Telegram alerts</li></ul></div><Link className="auth-back" href="/">← Back to home</Link></section><section className="auth-content">{children}</section></main>;
}
