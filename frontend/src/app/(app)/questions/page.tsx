import type { Metadata } from "next";
import { Suspense } from "react";

import { QuestionBank } from "@/components/questions/question-bank";

export const metadata: Metadata = { title: "Question bank · CareerLens" };

export default function QuestionsPage() {
  return (
    <Suspense>
      <QuestionBank />
    </Suspense>
  );
}
