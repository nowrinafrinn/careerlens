import type { Metadata } from "next";
import { Suspense } from "react";

import { GapView } from "@/components/learning/gap-view";

export const metadata: Metadata = { title: "Skill gap · CareerLens" };

export default function GapPage() {
  return (
    <Suspense>
      <GapView />
    </Suspense>
  );
}
