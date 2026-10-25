import type { Metadata } from "next";
import { Suspense } from "react";

import { ApplicationDetail } from "@/components/applications/application-detail";

export const metadata: Metadata = { title: "Application · CareerLens" };

// The id is only known per request; with Cache Components, reading it must
// happen inside a Suspense boundary.
export default function ApplicationPage() {
  return (
    <Suspense>
      <ApplicationDetail />
    </Suspense>
  );
}
