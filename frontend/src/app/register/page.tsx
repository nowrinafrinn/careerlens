import type { Metadata } from "next";

import { AuthForm } from "@/components/auth-form";

export const metadata: Metadata = { title: "Create account · CareerLens" };

export default function RegisterPage() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-6 px-4 py-12">
      <p className="text-sm font-semibold tracking-tight">CareerLens</p>
      <AuthForm mode="register" />
    </main>
  );
}
