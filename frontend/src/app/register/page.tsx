import type { Metadata } from "next";

import { BrandMark } from "@/components/app-header";
import { AuthForm } from "@/components/auth-form";

export const metadata: Metadata = { title: "Create account · CareerLens" };

export default function RegisterPage() {
  return (
    <main className="page-depth flex flex-1 flex-col items-center justify-center gap-6 px-4 py-12">
      <p className="flex items-center gap-2 text-base font-bold tracking-tight">
        <BrandMark />
        CareerLens
      </p>
      <AuthForm mode="register" />
    </main>
  );
}
