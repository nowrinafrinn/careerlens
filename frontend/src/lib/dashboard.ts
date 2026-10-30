// Typed client for the dashboard and insights.

import { apiFetch } from "@/lib/api";
import type { components } from "@/lib/api-types";
import { daysUntil, describeDaysUntil, formatDateTime, formatLocalDate } from "@/lib/format";

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

export type NextStep = {
  title: string;
  detail: string;
  href: string;
  action: string;
  prep?: { done: number; total: number };
  attention?: Dashboard["needs_attention"][number]; // the overdue item this step came from
};

/**
 * The one thing to do next, from what the dashboard already knows: anything
 * overdue, then the nearest round still being prepared, a deadline within a
 * week, an analysis waiting for input, a result to record, then the top task.
 * The attention item it picks, if any, is left out of the attention list.
 */
export function pickNextStep(d: Dashboard): NextStep | null {
  const overdue = d.needs_attention.find((item) => item.application_id);
  if (overdue) {
    return {
      title:
        overdue.kind === "round_passed"
          ? `Record what happened in ${overdue.round_name}`
          : overdue.kind === "confirmation_passed"
            ? `Check ${overdue.round_name}`
            : `Update ${overdue.position_title}`,
      detail: `${overdue.company_name}: ${overdue.message}`,
      href: `/applications/${overdue.application_id}`,
      action: "Open the application",
      attention: overdue,
    };
  }
  const round = d.upcoming_rounds.find((r) => r.prep_total === 0 || r.prep_done < r.prep_total);
  if (round) {
    return {
      title: `Prepare for ${round.round_name}`,
      detail: `${round.position_title} at ${round.company_name} · ${formatDateTime(round.scheduled_at)} · ${describeDaysUntil(daysUntil(formatLocalDate(round.scheduled_at)))}`,
      href: `/applications/${round.application_id}/prepare?round=${round.round_id}`,
      action: "Continue preparing",
      prep: { done: round.prep_done, total: round.prep_total },
    };
  }
  const deadline = d.upcoming_deadlines.find((a) => daysUntil(a.date) <= 7);
  if (deadline) {
    return {
      title: `Apply: ${deadline.position_title}`,
      detail: `${deadline.company_name} · deadline ${describeDaysUntil(daysUntil(deadline.date))}`,
      href: `/applications/${deadline.application_id}`,
      action: "Open the application",
    };
  }
  const analysis = d.analyses.find((a) => a.needs_your_input > 0);
  if (analysis) {
    return {
      title: `Assess ${analysis.needs_your_input} requirement${analysis.needs_your_input === 1 ? "" : "s"}`,
      detail: `${analysis.position_title} at ${analysis.company_name}: your CV doesn't fully show these`,
      href: `/applications/${analysis.application_id}/analysis`,
      action: "Open the analysis",
    };
  }
  const pending = d.pending_results[0];
  if (pending) {
    return {
      title: `Record the result of ${pending.round_name}`,
      detail: pending.company_name,
      href: `/applications/${pending.application_id}`,
      action: "Open the application",
    };
  }
  const task = d.top_tasks[0];
  if (task?.skill_gap_id) {
    return { title: task.title, detail: "Your top learning task", href: `/learning/${task.skill_gap_id}`, action: "Open the task" };
  }
  return null;
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
