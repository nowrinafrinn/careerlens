import type { Metadata } from "next";
import { Suspense } from "react";

import { EditJournal } from "@/components/journals/edit-journal";

export const metadata: Metadata = { title: "Edit journal · CareerLens" };

export default function EditJournalPage() {
  return (
    <Suspense>
      <EditJournal />
    </Suspense>
  );
}
