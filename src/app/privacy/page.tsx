import { TrustPage, TrustSection } from "@/components/trust-page";
export const metadata = { title: "Privacy" };
export default function PrivacyPage() { return <TrustPage eyebrow="Your data" title="Privacy at Sprintern" intro="Sprintern keeps only the information needed to match internships, deliver alerts, and help you track applications.">
  <TrustSection title="What we store"><p>Your account email, timezone, notification preferences, optional Telegram chat identifier, filters, matches, application status, and notification delivery history.</p></TrustSection>
  <TrustSection title="How we use it"><p>We use this information to authenticate you, run your filters, prevent duplicate alerts, deliver notifications you enable, and show your application activity. We do not sell personal information.</p></TrustSection>
  <TrustSection title="Services involved"><p>Supabase provides authentication and database services. Telegram and Resend receive the minimum delivery information required when you enable those channels. GitHub repositories provide public job-posting data.</p></TrustSection>
  <TrustSection title="Your choices"><p>You can disable notifications, disconnect Telegram, export your Sprintern data, or permanently delete your account from Settings.</p></TrustSection>
  <TrustSection title="Retention and questions"><p>Account data is retained while your account is active. Operational logs are limited and exclude credentials. Contact support with privacy or deletion questions.</p></TrustSection>
</TrustPage>; }
