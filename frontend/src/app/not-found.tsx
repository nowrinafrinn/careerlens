import type { Metadata } from "next";
import Link from "next/link";

import { BrandMark } from "@/components/app-header";
import { buttonClass } from "@/lib/button-class";

export const metadata: Metadata = { title: "Page not found · CareerLens" };

export default function NotFound() {
  return (
    <main className="page-depth flex flex-1 flex-col items-center justify-center gap-6 px-4 py-12 text-center">
      <p className="flex items-center gap-2 text-base font-bold tracking-tight">
        <BrandMark />
        CareerLens
      </p>
      <div className="surface no-lift flex max-w-sm flex-col items-center gap-3 rounded-2xl border p-8">
        <h1 className="text-xl font-semibold">Page not found</h1>
        <p className="text-sm text-muted-foreground">This address doesn&apos;t match any page. It may be mistyped or out of date.</p>
        <Link href="/" className={buttonClass()}>
          Go to the dashboard
        </Link>
      </div>
    </main>
  );
}
