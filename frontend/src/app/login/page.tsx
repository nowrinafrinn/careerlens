import type { Metadata } from "next";

import { AuthForm } from "@/components/auth-form";

export const metadata: Metadata = { title: "Sign in · CareerLens" };

export default function LoginPage() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-6 px-4 py-12">
      <p className="text-sm font-semibold tracking-tight">CareerLens</p>
      <AuthForm mode="login" />
    </main>
  );
}
