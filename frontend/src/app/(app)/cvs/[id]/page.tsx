import type { Metadata } from "next";
import { Suspense } from "react";

import { CVReview } from "@/components/cvs/cv-review";

export const metadata: Metadata = { title: "CV review · CareerLens" };

export default function CVReviewPage() {
  return (
    <Suspense>
      <CVReview />
    </Suspense>
  );
}
