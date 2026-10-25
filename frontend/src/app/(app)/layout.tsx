import Link from "next/link";
import { Suspense } from "react";

import { AppHeader, BrandMark } from "@/components/app-header";
import { PageTransition } from "@/components/page-transition";

const STAGE_ID = "page-stage";

// Shared frame for every signed-in page. The (app) folder is a route group:
// it shapes the layout without appearing in URLs.
export default function AppLayout({ children }: LayoutProps<"/">) {
  return (
    <>
      {/* The header highlights the current page (usePathname), which is only
          known per request on dynamic routes, so it streams in behind a
          same-sized placeholder. The page transition reads it too. */}
      <Suspense fallback={<HeaderPlaceholder />}>
        <AppHeader />
      </Suspense>
      <Suspense fallback={null}>
        <PageTransition stageId={STAGE_ID} />
      </Suspense>
      {/* Bottom padding below lg keeps content clear of the floating tab bar. */}
      <main
        id={STAGE_ID}
        className="mx-auto flex w-full max-w-6xl flex-1 origin-top flex-col px-4 pt-6 pb-28 sm:px-6 sm:pt-8 lg:pb-10"
      >
        {children}
      </main>
    </>
  );
}

function HeaderPlaceholder() {
  return (
    <header className="sticky top-3 z-40 mx-3 mt-3 sm:mx-4">
      <div className="surface no-lift mx-auto flex h-14 w-full max-w-6xl items-center rounded-2xl border px-4">
        <Link href="/" className="flex items-center gap-2 text-sm font-bold tracking-tight">
          <BrandMark />
          CareerLens
        </Link>
      </div>
    </header>
  );
}
