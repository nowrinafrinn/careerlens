import type { Metadata } from "next";

import { CVList } from "@/components/cvs/cv-list";

export const metadata: Metadata = { title: "CVs · CareerLens" };

export default function CVsPage() {
  return <CVList />;
}
