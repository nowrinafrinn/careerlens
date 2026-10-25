import type { Metadata } from "next";
import { Suspense } from "react";

import { JournalView } from "@/components/journals/journal-view";

export const metadata: Metadata = { title: "Journal · CareerLens" };

export default function JournalPage() {
  return (
    <Suspense>
      <JournalView />
    </Suspense>
  );
}
