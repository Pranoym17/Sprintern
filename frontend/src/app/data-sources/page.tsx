import { TrustPage, TrustSection } from "@/components/trust-page";
export const metadata = { title: "Data sources" };
export default function DataSourcesPage() { return <TrustPage eyebrow="Transparent sourcing" title="Where postings come from" intro="Sprintern monitors community-maintained GitHub repositories and preserves the original application destination for each posting.">
  <TrustSection title="Community repositories"><p>Repository maintainers collect and update public internship listings. Sprintern is not affiliated with those maintainers and does not claim ownership of their work. Source links remain attached for traceability and attribution.</p></TrustSection>
  <TrustSection title="Normalization"><p>Sprintern normalizes company, title, location, term, and work mode, then merges overlapping listings while retaining each source record.</p></TrustSection>
  <TrustSection title="Direct applications"><p>Sprintern prefers the original employer or applicant-tracking-system link. Always inspect the destination before providing personal information.</p></TrustSection>
  <TrustSection title="Limitations"><p>Public tables can change format or become stale. Postings may close before a source is updated, and inferred terms may be unknown. Sprintern surfaces freshness and fails visibly when a source cannot be processed.</p></TrustSection>
</TrustPage>; }
