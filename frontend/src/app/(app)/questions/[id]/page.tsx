import type { Metadata } from "next";
import { Suspense } from "react";

import { QuestionDetail } from "@/components/questions/question-detail";

export const metadata: Metadata = { title: "Question · CareerLens" };

export default function QuestionPage() {
  return (
    <Suspense>
      <QuestionDetail />
    </Suspense>
  );
}
