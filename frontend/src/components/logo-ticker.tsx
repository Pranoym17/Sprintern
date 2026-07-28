import Image from "next/image";

type Logo = { name: string; logo: string };

export function LogoTicker({ logos }: { logos: Logo[] }) {
  const track = [...logos, ...logos];
  return (
    <div className="logo-ticker" aria-label={`Companies watched: ${logos.map((logo) => logo.name).join(", ")}`}>
      <div className="logo-ticker__track">
        {track.map((logo, index) => (
          <Image
            key={`${logo.name}-${index}`}
            className="logo-ticker__logo"
            src={logo.logo}
            alt=""
            aria-hidden="true"
            width={137}
            height={40}
          />
        ))}
      </div>
    </div>
  );
}
