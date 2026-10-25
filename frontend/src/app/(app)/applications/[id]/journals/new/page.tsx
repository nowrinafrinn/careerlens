import type { Metadata } from "next";
import { Suspense } from "react";

import { NewJournal } from "@/components/journals/new-journal";

export const metadata: Metadata = { title: "Write a journal · CareerLens" };

export default function NewJournalPage() {
  return (
    <Suspense>
      <NewJournal />
    </Suspense>
  );
}
