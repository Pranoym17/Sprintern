import { Suspense } from "react";
import { MatchesView } from "@/components/matches-view";
import { MatchesSkeleton } from "@/components/page-state";

export const metadata = { title: "Matches" };

export default function Matches() {
  return <Suspense fallback={<MatchesSkeleton />}><MatchesView /></Suspense>;
}
