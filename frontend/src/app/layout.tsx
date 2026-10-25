import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { Providers } from "@/components/providers";

import "./globals.css";

// globals.css maps Tailwind's font-sans / font-mono to these variables.
const geistSans = Geist({
  variable: "--font-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "CareerLens",
  description: "Evidence-based career intelligence: job requirements, CV evidence, preparation and recruitment tracking.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      // Solid background on <html>; the body's light tint sits on top of it. A
      // translucent background alone would show whatever is behind the page.
      className={`${geistSans.variable} ${geistMono.variable} h-full bg-background antialiased`}
    >
      <body className="min-h-full flex flex-col bg-muted/30">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
