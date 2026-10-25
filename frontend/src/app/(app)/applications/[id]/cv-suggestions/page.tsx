import type { Metadata } from "next";
import { Suspense } from "react";

import { RecommendationsView } from "@/components/recommendations/recommendations-view";

export const metadata: Metadata = { title: "CV suggestions · CareerLens" };

export default function CVSuggestionsPage() {
  return (
    <Suspense>
      <RecommendationsView />
    </Suspense>
  );
}
