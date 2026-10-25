// Typed client for the dashboard and insights.

import { apiFetch } from "@/lib/api";
import type { components } from "@/lib/api-types";

type Schemas = components["schemas"];

export type Dashboard = Schemas["DashboardRead"];
export type Insights = Schemas["InsightsRead"];
export type Insight = Schemas["InsightRead"];
export type InsightSource = Schemas["InsightSource"];

export const dashboardKeys = {
  dashboard: (today: string) => ["dashboard", today] as const,
  insights: ["insights"] as const,
};

/** The browser's local date, so "overdue" matches the user's calendar, not the server's UTC day. */
export function localToday(): string {
  return new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD
}

export const getDashboard = (today: string) => apiFetch<Dashboard>(`/dashboard?${new URLSearchParams({ today })}`);
export const getInsights = () => apiFetch<Insights>("/insights");

export function sourceHref(source: InsightSource): string | null {
  switch (source.kind) {
    case "application":
      return `/applications/${source.id}`;
    case "question":
      return `/questions/${source.id}`;
    case "skill_gap":
      return `/learning/${source.id}`;
    case "requirement":
      return source.application_id ? `/applications/${source.application_id}/analysis` : null;
    default:
      return null;
  }
}

export const INSIGHT_BASIS: Record<Insight["basis"], string> = {
  job_descriptions: "From job descriptions",
  cv_analysis: "From your CV analyses",
  recorded_outcomes: "From your recorded outcomes",
  your_statements: "From your own statements",
  mixed: "From several kinds of records",
};
