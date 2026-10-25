import type { Metadata } from "next";

import { SystemStatus } from "@/components/system-status";

export const metadata: Metadata = { title: "System status · CareerLens" };

export default function StatusPage() {
  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <h1 className="text-xl font-semibold tracking-tight">System status</h1>
      <SystemStatus />
      <p className="text-sm text-muted-foreground">
        API documentation:{" "}
        <a href="/api/docs" className="font-medium text-foreground underline underline-offset-4">
          /api/docs
        </a>
      </p>
    </div>
  );
}
