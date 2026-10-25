import type { Metadata } from "next";
import { Suspense } from "react";

import { EditApplication } from "@/components/applications/edit-application";

export const metadata: Metadata = { title: "Edit application · CareerLens" };

export default function EditApplicationPage() {
  return (
    <Suspense>
      <EditApplication />
    </Suspense>
  );
}
