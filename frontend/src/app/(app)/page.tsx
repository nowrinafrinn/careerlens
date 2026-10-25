import type { Metadata } from "next";
import { Suspense } from "react";

import { DashboardView } from "@/components/dashboard/dashboard-view";

export const metadata: Metadata = { title: "Dashboard · CareerLens" };

export default function DashboardPage() {
  // The dashboard reads the browser's local date, which only exists per visit.
  return (
    <Suspense fallback={<div aria-hidden className="h-96 animate-pulse rounded-xl bg-muted" />}>
      <DashboardView />
    </Suspense>
  );
}
