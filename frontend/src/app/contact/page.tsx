import { TrustPage, TrustSection } from "@/components/trust-page";
export const metadata = { title: "Contact" };
const supportEmail = process.env.NEXT_PUBLIC_SUPPORT_EMAIL ?? "support@sprintern.app";
export default function ContactPage() { return <TrustPage eyebrow="Support" title="Contact Sprintern" intro="Questions, data requests, broken application links, and responsible security reports are welcome.">
  <TrustSection title="How to reach us"><p>Email <a className="inline-link" href={`mailto:${supportEmail}`}>{supportEmail}</a>. Include the affected page or employer name, but never send passwords, access tokens, or API keys.</p></TrustSection>
  <TrustSection title="Data requests"><p>You can export or delete your data directly in Settings. If that is unavailable, contact support from the email address on your account.</p></TrustSection>
  <TrustSection title="Job corrections"><p>Sprintern reflects community-maintained sources. Report broken or misleading listings and confirm the current status on the employer’s official website.</p></TrustSection>
</TrustPage>; }
