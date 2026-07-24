import { TrustPage, TrustSection } from "@/components/trust-page";
export const metadata = { title: "Job data and accuracy" };
export default function DataSourcesPage() { return <TrustPage eyebrow="Job data & accuracy" title="How Sprintern handles postings" intro="Sprintern turns public internship information into one consistent feed and preserves the original employer application destination.">
  <TrustSection title="Normalization"><p>Sprintern normalizes company, title, location, term, and work mode, then merges overlapping listings before they reach your feed.</p></TrustSection>
  <TrustSection title="Direct applications"><p>Sprintern prefers the original employer or applicant-tracking-system link. Always inspect the destination before providing personal information.</p></TrustSection>
  <TrustSection title="Limitations"><p>Public job information can change or become stale. Postings may close before Sprintern detects the change, and inferred terms may be unknown. Freshness checks fail visibly instead of silently dropping updates.</p></TrustSection>
</TrustPage>; }
