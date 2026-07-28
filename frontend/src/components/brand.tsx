import Image from "next/image";
import Link from "next/link";

export function Brand({ href = "/" }: { href?: string }) {
  return (
    <Link className="brand" href={href} aria-label="Sprintern home">
      <span className="brand__emblem" aria-hidden="true">
        <Image
          src="/brand/sprintern-metallic.png"
          alt=""
          width={685}
          height={384}
          priority
        />
      </span>
      <span className="brand__word">Sprintern</span>
    </Link>
  );
}
