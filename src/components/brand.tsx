import Link from "next/link";
import { Radar } from "lucide-react";

export function Brand({ href = "/" }: { href?: string }) {
  return <Link className="brand" href={href} aria-label="Sprintern home"><span className="brand__mark"><Radar size={20} /></span><span>Sprintern</span></Link>;
}
