import Image from "next/image";

const companyLogos = [
  [["google", "alphabet"], "google"],
  [["apple"], "apple"],
  [["nvidia"], "nvidia"],
  [["shopify"], "shopify"],
  [["meta", "facebook"], "meta"],
  [["airbnb"], "airbnb"],
  [["amd", "advanced micro devices"], "amd"],
  [["atlassian"], "atlassian"],
  [["cloudflare"], "cloudflare"],
  [["coinbase"], "coinbase"],
  [["datadog"], "datadog"],
  [["digitalocean"], "digitalocean"],
  [["discord"], "discord"],
  [["docker"], "docker"],
  [["doordash"], "doordash"],
  [["dropbox"], "dropbox"],
  [["gitlab"], "gitlab"],
  [["intel"], "intel"],
  [["mongodb"], "mongodb"],
  [["paypal"], "paypal"],
  [["pinterest"], "pinterest"],
  [["reddit"], "reddit"],
  [["sap"], "sap"],
  [["snowflake"], "snowflake"],
  [["spotify"], "spotify"],
  [["stripe"], "stripe"],
  [["tesla"], "tesla"],
  [["zoom"], "zoom"],
] as const;

export function logoPathForCompany(company: string): string | null {
  const normalized = ` ${company.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim()} `;
  const match = companyLogos.find(([aliases]) =>
    aliases.some((alias) => normalized.includes(` ${alias} `)),
  );
  return match ? `/company-logos/${match[1]}.svg` : null;
}

export function CompanyLogo({
  company,
  size = "medium",
}: {
  company: string;
  size?: "small" | "medium" | "large";
}) {
  const logo = logoPathForCompany(company);
  const initials = company
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
  return <span className={`company-mark company-mark--${size}`} aria-hidden="true">
    {logo
      ? <Image src={logo} alt="" width={44} height={44} />
      : <span>{initials || "—"}</span>}
  </span>;
}
