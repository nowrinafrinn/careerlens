import type { Metadata } from "next";
import { Suspense } from "react";

import { ApplicationsList } from "@/components/applications/applications-list";

export const metadata: Metadata = { title: "Applications · CareerLens" };

export default function ApplicationsPage() {
  // The list reads its filters from the URL (useSearchParams), which is only
  // known per request, so it renders inside a Suspense boundary.
  return (
    <Suspense>
      <ApplicationsList />
    </Suspense>
  );
}
