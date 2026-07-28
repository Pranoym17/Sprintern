import Link from "next/link";

export function Brand({ href = "/" }: { href?: string }) {
  return (
    <Link className="brand" href={href} aria-label="Sprintern home">
      <span className="brand__mark" aria-hidden="true"><i /><i /><i /></span>
      <span>Sprintern</span>
    </Link>
  );
}
