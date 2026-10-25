"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { currentUserKey, getCurrentUser, logout } from "@/lib/auth";

const NAV = [{ href: "/applications", label: "Applications" }];

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

  return (
    <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/80">
      <div className="mx-auto flex h-14 w-full max-w-6xl items-center gap-6 px-4 sm:px-6">
        <Link href="/applications" className="text-sm font-semibold tracking-tight">
          CareerLens
        </Link>
        <nav aria-label="Main" className="flex items-center gap-1">
          {NAV.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className="rounded-md px-2.5 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground aria-[current=page]:bg-muted aria-[current=page]:font-medium aria-[current=page]:text-foreground"
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex min-w-0 items-center gap-3">
          <span className="hidden truncate text-sm text-muted-foreground sm:inline">
            {user ? (user.display_name ?? user.email) : ""}
          </span>
          <Button variant="outline" size="sm" onClick={signOut} disabled={signingOut}>
            {signingOut ? "Signing out…" : "Sign out"}
          </Button>
        </div>
      </div>
    </header>
  );
}
