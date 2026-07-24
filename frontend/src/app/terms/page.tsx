import { TrustPage, TrustSection } from "@/components/trust-page";
export const metadata = { title: "Terms" };
export default function TermsPage() { return <TrustPage eyebrow="Plain-language terms" title="Terms of use" intro="Use Sprintern as a discovery and tracking aid, then verify every opportunity with the employer before applying.">
  <TrustSection title="The service"><p>Sprintern aggregates public internship postings, applies your filters, and sends optional alerts. Features and sources may change as public repositories change.</p></TrustSection>
  <TrustSection title="Your responsibility"><p>Keep your account secure, provide accurate preferences, and use the service lawfully. Do not disrupt the service, bypass access controls, or misuse employer application systems.</p></TrustSection>
  <TrustSection title="Job accuracy"><p>Postings may be incomplete, duplicated, changed, or expired. Sprintern does not guarantee availability, eligibility, accuracy, interviews, or employment. The employer’s application page is authoritative.</p></TrustSection>
  <TrustSection title="No affiliation"><p>Sprintern is an independent service. It is not affiliated with, endorsed by, or acting for repository maintainers, listed employers, or its service providers.</p></TrustSection>
  <TrustSection title="Availability"><p>The service is provided as available and may be changed, paused, or discontinued. These terms do not remove rights that cannot legally be waived.</p></TrustSection>
</TrustPage>; }
