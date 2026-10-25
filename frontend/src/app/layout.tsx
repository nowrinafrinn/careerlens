import type { Metadata, Viewport } from "next";
import { Fira_Code, Fira_Sans } from "next/font/google";

import { Providers } from "@/components/providers";

import "./globals.css";

// globals.css maps Tailwind's font-sans / font-mono to these variables.
const firaSans = Fira_Sans({
  variable: "--font-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const firaCode = Fira_Code({
  variable: "--font-fira-code",
  subsets: ["latin"],
  weight: ["500", "600"],
});

export const metadata: Metadata = {
  title: "CareerLens",
  description: "Evidence-based career intelligence: job requirements, CV evidence, preparation and recruitment tracking.",
};

// Browser chrome matches the device's light or dark setting.
export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#eef2f7" },
    { media: "(prefers-color-scheme: dark)", color: "#0b1120" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // The solid page colour sits on <html>; globals.css paints the glow, dot
    // grid and 3D floor behind <body>, and glass surfaces float above them.
    <html lang="en" className={`${firaSans.variable} ${firaCode.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
