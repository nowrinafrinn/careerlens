import Link from "next/link";
import { Suspense } from "react";

import { AppHeader } from "@/components/app-header";

// Shared frame for every signed-in page. The (app) folder is a route group:
// it shapes the layout without appearing in URLs.
export default function AppLayout({ children }: LayoutProps<"/">) {
  return (
    <>
      {/* The header highlights the current page (usePathname), which is only
          known per request on dynamic routes, so it streams in behind a
          same-sized placeholder. */}
      <Suspense fallback={<HeaderPlaceholder />}>
        <AppHeader />
      </Suspense>
      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-6 sm:px-6 sm:py-8">{children}</main>
    </>
  );
}

function HeaderPlaceholder() {
  return (
    <header className="sticky top-0 z-40 border-b bg-background">
      <div className="mx-auto flex h-14 w-full max-w-6xl items-center px-4 sm:px-6">
        <Link href="/applications" className="text-sm font-semibold tracking-tight">
          CareerLens
        </Link>
      </div>
    </header>
  );
}
