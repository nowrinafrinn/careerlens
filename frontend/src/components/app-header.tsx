"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Briefcase, CircleHelp, FileText, House, Sparkles, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { currentUserKey, getCurrentUser, logout } from "@/lib/auth";

type NavItem = { href: string; label: string; short: string; icon: LucideIcon; inTabBar: boolean };

const NAV: NavItem[] = [
  { href: "/", label: "Dashboard", short: "Home", icon: House, inTabBar: true },
  { href: "/applications", label: "Applications", short: "Apps", icon: Briefcase, inTabBar: true },
  { href: "/cvs", label: "CVs", short: "CVs", icon: FileText, inTabBar: false },
  { href: "/questions", label: "Questions", short: "Questions", icon: CircleHelp, inTabBar: true },
  { href: "/learning", label: "Learning", short: "Learning", icon: BookOpen, inTabBar: true },
  { href: "/insights", label: "Insights", short: "Insights", icon: Sparkles, inTabBar: true },
];

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

/** The CareerLens lens mark. */
export function BrandMark() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden className="size-5.5 text-primary">
      <circle cx="12" cy="12" r="8.5" />
      <circle cx="12" cy="12" r="3.5" />
      <path d="M12 3.5v5M20.5 12h-5" />
    </svg>
  );
}

export function AppHeader() {
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const { data: user } = useQuery({ queryKey: currentUserKey, queryFn: getCurrentUser, staleTime: 5 * 60_000 });
  const [signingOut, setSigningOut] = useState(false);

  async function signOut() {
    setSigningOut(true);
    try {
      await logout();
    } finally {
      queryClient.clear(); // drop every cached record of this user
      // A full page load, not router.push: Next.js keeps recently visited pages
      // mounted (hidden) with this user's data. Reloading wipes all of it.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.assign("/login");
    }
  }

  const name = user ? (user.display_name ?? user.email) : "";
  const cvsActive = isActive(pathname, "/cvs");

  return (
    <>
      <header className="sticky top-3 z-40 mx-3 mt-3 sm:mx-4">
        <div className="surface no-lift mx-auto flex h-14 w-full max-w-6xl items-center gap-6 rounded-2xl border pr-2 pl-4 sm:pr-3">
          <Link href="/" className="flex shrink-0 items-center gap-2 text-sm font-bold tracking-tight pointer-coarse:min-h-11">
            <BrandMark />
            CareerLens
          </Link>
          <nav aria-label="Main" className="hidden items-center gap-0.5 lg:flex">
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                aria-current={isActive(pathname, item.href) ? "page" : undefined}
                className="rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground aria-[current=page]:bg-primary/12 aria-[current=page]:font-semibold aria-[current=page]:text-foreground"
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex min-w-0 items-center gap-2 sm:gap-3">
            {/* On phones CVs isn't in the tab bar, so it gets an icon here. */}
            <Link
              href="/cvs"
              aria-label="CVs"
              aria-current={cvsActive ? "page" : undefined}
              className="grid size-11 place-items-center rounded-xl text-muted-foreground hover:bg-muted hover:text-foreground aria-[current=page]:bg-primary/12 aria-[current=page]:text-primary lg:hidden"
            >
              <FileText className="size-5" aria-hidden />
            </Link>
            <span className="hidden truncate text-sm text-muted-foreground xl:inline">{name}</span>
            <span
              aria-hidden
              className="grid size-8 shrink-0 place-items-center rounded-full bg-primary text-xs font-bold text-primary-foreground uppercase"
            >
              {name.slice(0, 1)}
            </span>
            <Button variant="outline" size="sm" onClick={signOut} disabled={signingOut}>
              {signingOut ? "Signing out…" : "Sign out"}
            </Button>
          </div>
        </div>
      </header>

      <nav
        aria-label="Main"
        className="surface no-lift fixed inset-x-3 bottom-3 z-40 flex justify-around rounded-3xl border p-1.5 lg:hidden"
      >
        {NAV.filter((item) => item.inTabBar).map((item) => {
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={isActive(pathname, item.href) ? "page" : undefined}
              className="flex min-h-12 min-w-14 flex-col items-center justify-center gap-0.5 rounded-2xl text-[11px] font-medium text-muted-foreground aria-[current=page]:bg-primary/12 aria-[current=page]:font-semibold aria-[current=page]:text-primary"
            >
              <Icon className="size-5" aria-hidden />
              {item.short}
            </Link>
          );
        })}
      </nav>
    </>
  );
}
