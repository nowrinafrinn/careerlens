import type { Metadata } from "next";

import { LearningPlan } from "@/components/learning/learning-plan";

export const metadata: Metadata = { title: "Learning plan · CareerLens" };

export default function LearningPage() {
  return <LearningPlan />;
}
