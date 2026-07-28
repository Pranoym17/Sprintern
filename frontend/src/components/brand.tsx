import Image from "next/image";
import Link from "next/link";

export function Brand({ href = "/" }: { href?: string }) {
  return (
    <Link className="brand" href={href} aria-label="Sprintern home">
      <span className="brand__lockup" aria-hidden="true">
        <Image
          src="/brand/sprintern-metallic.png"
          alt=""
          width={1056}
          height={600}
          priority
        />
      </span>
    </Link>
  );
}
