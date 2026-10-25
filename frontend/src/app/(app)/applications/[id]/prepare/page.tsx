import type { Metadata } from "next";
import { Suspense } from "react";

import { PrepareView } from "@/components/preparation/prepare-view";

export const metadata: Metadata = { title: "Prepare · CareerLens" };

export default function PreparePage() {
  return (
    <Suspense>
      <PrepareView />
    </Suspense>
  );
}
