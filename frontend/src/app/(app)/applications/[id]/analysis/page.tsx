import type { Metadata } from "next";
import { Suspense } from "react";

import { AnalysisView } from "@/components/analysis/analysis-view";

export const metadata: Metadata = { title: "Requirements and CV evidence · CareerLens" };

export default function AnalysisPage() {
  return (
    <Suspense>
      <AnalysisView />
    </Suspense>
  );
}
