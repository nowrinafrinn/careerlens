"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { getCurrentUser, logout, type User } from "@/lib/auth";

/**
 * Shows who is signed in and a sign-out button. If the backend says the
 * session is invalid (expired, revoked), it sends the user to /login.
 */
export function AccountBar() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [signingOut, setSigningOut] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getCurrentUser().then(
      (me) => {
        if (!cancelled) setUser(me);
      },
      (error) => {
        if (!cancelled && error instanceof ApiError && error.status === 401) {
          router.replace(`/login?next=${encodeURIComponent(window.location.pathname)}`);
        }
      },
    );
    return () => {
      cancelled = true;
    };
  }, [router]);

  async function signOut() {
    setSigningOut(true);
    try {
      await logout();
    } finally {
      router.replace("/login");
      router.refresh();
    }
  }

  return (
    <div className="flex items-center justify-between gap-4 border-b px-4 py-3 sm:px-6">
      <span className="text-sm font-semibold tracking-tight">CareerLens</span>
      <div className="flex min-w-0 items-center gap-3">
        <span className="truncate text-sm text-muted-foreground" aria-live="polite">
          {user ? (user.display_name ?? user.email) : ""}
        </span>
        <Button variant="outline" size="sm" onClick={signOut} disabled={!user || signingOut}>
          {signingOut ? "Signing out…" : "Sign out"}
        </Button>
      </div>
    </div>
  );
}
