import type { Metadata } from "next";
import Link from "next/link";

import { ApplicationForm } from "@/components/applications/application-form";

export const metadata: Metadata = { title: "New application · CareerLens" };

export default function NewApplicationPage() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <div className="flex flex-col gap-1">
        <Link href="/applications" className="text-sm text-muted-foreground hover:text-foreground">
          ← Applications
        </Link>
        <h1 className="text-xl font-semibold tracking-tight">New application</h1>
        <p className="text-sm text-muted-foreground">
          Only the position and company are required. You can save a job now and fill in the rest later.
        </p>
      </div>
      <ApplicationForm />
    </div>
  );
}
