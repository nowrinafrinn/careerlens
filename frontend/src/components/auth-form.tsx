"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { login, register, safeNextPath } from "@/lib/auth";

type Mode = "login" | "register";

const COPY: Record<Mode, { title: string; description: string; submit: string; busy: string }> = {
  login: {
    title: "Sign in",
    description: "Continue with your applications, evidence and preparation.",
    submit: "Sign in",
    busy: "Signing in…",
  },
  register: {
    title: "Create your account",
    description: "Your records are private to your account.",
    submit: "Create account",
    busy: "Creating account…",
  },
};

function messageFor(error: unknown): string {
  if (!(error instanceof ApiError)) return "Something went wrong. Please try again.";
  if (error.code === "validation_error") {
    return "Check the email address, and use a password of 8 to 128 characters.";
  }
  return error.message;
}

export function AuthForm({ mode }: { mode: Mode }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const copy = COPY[mode];

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "");
    const password = String(form.get("password") ?? "");

    setSubmitting(true);
    setError(null);
    try {
      if (mode === "login") {
        await login({ email, password });
      } else {
        const displayName = String(form.get("display_name") ?? "").trim();
        await register({ email, password, display_name: displayName || undefined });
      }
      const next = safeNextPath(new URLSearchParams(window.location.search).get("next"));
      router.replace(next);
      router.refresh();
    } catch (err) {
      setError(messageFor(err));
      setSubmitting(false);
    }
  }

  return (
    <Card className="surface float-forward w-full max-w-sm">
      <CardHeader>
        <CardTitle className="text-lg">{copy.title}</CardTitle>
        <CardDescription>{copy.description}</CardDescription>
      </CardHeader>
      <form onSubmit={onSubmit} noValidate={false}>
        <CardContent className="flex flex-col gap-4">
          {mode === "register" && (
            <div className="flex flex-col gap-2">
              <Label htmlFor="display_name">
                Name <span className="font-normal text-muted-foreground">(optional)</span>
              </Label>
              <Input id="display_name" name="display_name" autoComplete="name" maxLength={100} />
            </div>
          )}
          <div className="flex flex-col gap-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" name="email" type="email" autoComplete="email" required />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              name="password"
              type="password"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              minLength={mode === "register" ? 8 : undefined}
              maxLength={128}
              required
              aria-describedby={mode === "register" ? "password-hint" : undefined}
            />
            {mode === "register" && (
              <p id="password-hint" className="text-xs text-muted-foreground">
                At least 8 characters.
              </p>
            )}
          </div>
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
        </CardContent>
        <CardFooter className="mt-4 flex flex-col items-stretch gap-3">
          <Button type="submit" disabled={submitting}>
            {submitting ? copy.busy : copy.submit}
          </Button>
          <p className="text-center text-sm text-muted-foreground">
            {mode === "login" ? (
              <>
                No account yet?{" "}
                <Link href="/register" className="font-medium text-foreground underline underline-offset-4">
                  Create one
                </Link>
              </>
            ) : (
              <>
                Already registered?{" "}
                <Link href="/login" className="font-medium text-foreground underline underline-offset-4">
                  Sign in
                </Link>
              </>
            )}
          </p>
        </CardFooter>
      </form>
    </Card>
  );
}
