"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState, type ReactNode } from "react";

import { InsightCard } from "@/components/dashboard/insight-card";
import { Pill } from "@/components/applications/status-badge";
import { buttonClass } from "@/lib/button-class";
import { dashboardKeys, getDashboard, getInsights, localToday, type Dashboard } from "@/lib/dashboard";
import { daysUntil, describeDaysUntil, formatDate, formatDateTime } from "@/lib/format";
import { APPLICATION_STATUS, APPLICATION_STATUS_ORDER, GAP_STATUS, PRACTICE_STATUS, TASK_STATUS } from "@/lib/labels";
import type { ApplicationStatus } from "@/lib/applications";
import type { GapStatus } from "@/lib/learning";

function Card({ title, action, children, className = "" }: { title: string; action?: ReactNode; children: ReactNode; className?: string }) {
  const id = `card-${title.toLowerCase().replace(/[^a-z]+/g, "-")}`;
  return (
    <section aria-labelledby={id} className={`flex min-w-0 flex-col gap-3 rounded-xl border bg-background p-4 ${className}`}>
      <div className="flex items-center justify-between gap-2">
        <h2 id={id} className="text-sm font-semibold">
          {title}
        </h2>
        {action}
      </div>
      {children}
    </section>
  );
}

const Empty = ({ children }: { children: ReactNode }) => <p className="text-sm text-muted-foreground">{children}</p>;

export function DashboardView() {
  // Fixed once per visit: the user's local date.
  const [today] = useState(localToday);
  const dashboard = useQuery({ queryKey: dashboardKeys.dashboard(today), queryFn: () => getDashboard(today), staleTime: 0 });
  const insights = useQuery({ queryKey: dashboardKeys.insights, queryFn: getInsights, staleTime: 0 });

  if (dashboard.isPending) return <div aria-hidden className="h-96 animate-pulse rounded-xl bg-muted" />;
  if (dashboard.isError) {
    return (
      <p role="alert" className="text-sm text-destructive">
        The dashboard couldn&apos;t be loaded. Check that the backend is running, then refresh.
      </p>
    );
  }
  const d = dashboard.data;
  const activeCount = Object.values(d.application_counts).reduce((a, b) => a + b, 0);

  if (activeCount === 0 && d.top_tasks.length === 0 && d.recent_journals.length === 0) {
    return <Welcome />;
  }

  const shownInsights = (insights.data?.insights ?? []).slice(0, 3);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          {formatDate(d.today)} · {activeCount} active application{activeCount === 1 ? "" : "s"}
        </p>
      </div>

      <NeedsAttention items={d.needs_attention} />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Coming up" action={<span className="text-xs text-muted-foreground">next 14 days</span>}>
          {d.upcoming_rounds.length === 0 && d.upcoming_deadlines.length === 0 ? (
            <Empty>No rounds or application deadlines in the next two weeks.</Empty>
          ) : (
            <ul className="flex flex-col gap-2 text-sm">
              {d.upcoming_rounds.map((r) => (
                <li key={r.round_id} className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                  <Link href={`/applications/${r.application_id}`} className="min-w-0 hover:underline">
                    <span className="font-medium">{r.round_name}</span>
                    <span className="text-muted-foreground"> · {r.company_name}</span>
                  </Link>
                  <span className="flex items-center gap-2 text-xs text-muted-foreground tabular-nums">
                    {formatDateTime(r.scheduled_at)}
                    <Link href={`/applications/${r.application_id}/prepare?round=${r.round_id}`} className="font-medium text-foreground underline underline-offset-4">
                      {r.prep_total > 0 ? `Prep ${r.prep_done}/${r.prep_total}` : "Prepare"}
                    </Link>
                  </span>
                </li>
              ))}
              {d.upcoming_deadlines.map((a) => (
                <li key={`deadline-${a.application_id}`} className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                  <Link href={`/applications/${a.application_id}`} className="min-w-0 hover:underline">
                    <span className="font-medium">Apply: {a.position_title}</span>
                    <span className="text-muted-foreground"> · {a.company_name}</span>
                  </Link>
                  <span className="text-xs text-muted-foreground tabular-nums">
                    Deadline {formatDate(a.date)} ({describeDaysUntil(daysUntil(a.date))})
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Waiting on results">
          {d.pending_results.length === 0 && d.follow_ups.length === 0 ? (
            <Empty>No rounds waiting for a result.</Empty>
          ) : (
            <ul className="flex flex-col gap-2 text-sm">
              {d.pending_results.map((p) => (
                <li key={`pending-${p.round_id}`} className="flex flex-wrap items-baseline justify-between gap-x-3">
                  <Link href={`/applications/${p.application_id}`} className="min-w-0 hover:underline">
                    <span className="font-medium">{p.round_name}</span>
                    <span className="text-muted-foreground"> · {p.company_name}</span>
                  </Link>
                  <span className="text-xs text-muted-foreground tabular-nums">since {formatDate(p.since)}</span>
                </li>
              ))}
              {d.follow_ups.map((f) => (
                <li key={`follow-${f.round_id}`} className="flex flex-wrap items-baseline justify-between gap-x-3">
                  <Link href={`/applications/${f.application_id}`} className="min-w-0 hover:underline">
                    Follow up: <span className="font-medium">{f.round_name}</span>
                    <span className="text-muted-foreground"> · {f.company_name}</span>
                  </Link>
                  <span className={`text-xs tabular-nums ${f.overdue ? "text-destructive" : "text-muted-foreground"}`}>
                    {formatDate(f.date)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Applications" action={<Link href="/applications" className="text-xs underline underline-offset-4">All</Link>}>
          <div className="flex flex-wrap gap-1.5">
            {APPLICATION_STATUS_ORDER.filter((s) => d.application_counts[s]).map((s: ApplicationStatus) => (
              <Pill key={s} tone={APPLICATION_STATUS[s].tone}>{`${APPLICATION_STATUS[s].label}: ${d.application_counts[s]}`}</Pill>
            ))}
          </div>
          {d.analyses.length > 0 ? (
            <ul className="flex flex-col gap-2 text-sm">
              {d.analyses.slice(0, 4).map((a) => (
                <li key={a.analysis_id} className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                  <Link href={`/applications/${a.application_id}/analysis`} className="min-w-0 hover:underline">
                    <span className="font-medium">{a.position_title}</span>
                    <span className="text-muted-foreground"> · {a.company_name}</span>
                  </Link>
                  <span className="text-xs text-muted-foreground tabular-nums">
                    {a.required_total > 0 ? `CV shows ${a.demonstrated}/${a.required_total} required` : "No required lines"}
                    {a.needs_your_input > 0 && ` · ${a.needs_your_input} to assess`}
                    {a.is_stale && " · out of date"}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <Empty>No requirement analyses yet. Open an application with a job description and a CV to run one.</Empty>
          )}
        </Card>

        <LearningCard d={d} />

        <Card title="Insights" action={<Link href="/insights" className="text-xs underline underline-offset-4">All insights</Link>} className="lg:col-span-2">
          {insights.isPending ? (
            <div aria-hidden className="h-16 animate-pulse rounded bg-muted" />
          ) : shownInsights.length === 0 ? (
            <Empty>
              No patterns yet. They appear as you analyse more applications and record questions and practice.{" "}
              {insights.data?.data_notes[0]}
            </Empty>
          ) : (
            <ul className="grid gap-2 md:grid-cols-3">
              {shownInsights.map((insight) => (
                <InsightCard key={insight.key} insight={insight} compact />
              ))}
            </ul>
          )}
        </Card>

        <Card title="Recent journals" className="lg:col-span-2">
          {d.recent_journals.length === 0 ? (
            <Empty>After an assessment or interview, write a journal from the round on its application page.</Empty>
          ) : (
            <ul className="flex flex-col gap-2 text-sm">
              {d.recent_journals.map((j) => (
                <li key={j.journal_id} className="flex flex-wrap items-baseline justify-between gap-x-3">
                  <Link href={`/journals/${j.journal_id}`} className="min-w-0 hover:underline">
                    <span className="font-medium">{j.round_name ?? "Journal"}</span>
                    <span className="text-muted-foreground"> · {j.company_name}</span>
                  </Link>
                  <span className="text-xs text-muted-foreground tabular-nums">
                    {j.question_count} question{j.question_count === 1 ? "" : "s"} · {formatDateTime(j.created_at)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}

function NeedsAttention({ items }: { items: Dashboard["needs_attention"] }) {
  if (items.length === 0) {
    return (
      <p className="rounded-xl border bg-background px-4 py-3 text-sm text-muted-foreground">
        Nothing overdue. Deadlines, past rounds and tasks will show here when they need you.
      </p>
    );
  }
  return (
    <section aria-labelledby="attention-heading" className="flex flex-col gap-2 rounded-xl border border-amber-300 bg-amber-50/60 p-4 dark:border-amber-800 dark:bg-amber-950/40">
      <h2 id="attention-heading" className="text-sm font-semibold">
        Needs attention <span className="font-normal text-muted-foreground tabular-nums">({items.length})</span>
      </h2>
      <ul className="flex flex-col gap-1.5 text-sm">
        {items.map((item, index) => {
          const href = item.task_id
            ? null
            : item.application_id
              ? `/applications/${item.application_id}`
              : null;
          const label = item.title ?? [item.round_name, item.company_name].filter(Boolean).join(" · ") ?? "";
          return (
            <li key={`${item.kind}-${index}`} className="flex flex-wrap items-baseline gap-x-2">
              <span className="text-xs text-muted-foreground tabular-nums">{formatDate(item.date)}</span>
              {href ? (
                <Link href={href} className="font-medium hover:underline">
                  {label || item.position_title}
                </Link>
              ) : (
                <span className="font-medium">{label}</span>
              )}
              <span className="text-muted-foreground">{item.message}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function LearningCard({ d }: { d: Dashboard }) {
  const gapStatuses = (["open", "improving", "resolved"] as GapStatus[]).filter((s) => d.gap_counts[s]);
  return (
    <Card title="Learning" action={<Link href="/learning" className="text-xs underline underline-offset-4">Learning plan</Link>}>
      {gapStatuses.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {gapStatuses.map((s) => (
            <Pill key={s} tone={GAP_STATUS[s].tone}>{`${GAP_STATUS[s].label} gaps: ${d.gap_counts[s]}`}</Pill>
          ))}
        </div>
      )}
      {d.top_tasks.length === 0 ? (
        <Empty>No open tasks.</Empty>
      ) : (
        <ul className="flex flex-col gap-1.5 text-sm">
          {d.top_tasks.map((t) => {
            const href = t.skill_gap_id
              ? `/learning/${t.skill_gap_id}`
              : t.application_id
                ? `/applications/${t.application_id}/prepare${t.round_id ? `?round=${t.round_id}` : ""}`
                : null;
            return (
              <li key={t.task_id} className="flex flex-wrap items-baseline justify-between gap-x-3">
                {href ? (
                  <Link href={href} className="min-w-0 hover:underline">
                    {t.title}
                  </Link>
                ) : (
                  <span className="min-w-0">{t.title}</span>
                )}
                <span className="text-xs text-muted-foreground">
                  {t.kind === "preparation" ? "Prep" : "Learning"} · {TASK_STATUS[t.status].label}
                  {t.due_date && ` · due ${formatDate(t.due_date)}`}
                </span>
              </li>
            );
          })}
        </ul>
      )}
      {d.recent_reassessments.length > 0 && (
        <p className="text-xs text-muted-foreground">
          Latest progress: {d.recent_reassessments[0].skill_name} {GAP_STATUS[d.recent_reassessments[0].previous_status].label.toLowerCase()} →{" "}
          {GAP_STATUS[d.recent_reassessments[0].new_status].label.toLowerCase()}
        </p>
      )}
      {d.questions_to_practice_total > 0 && (
        <div className="border-t pt-2 text-sm">
          <Link href="/questions?practice_status=to_practice" className="font-medium hover:underline">
            {d.questions_to_practice_total} question{d.questions_to_practice_total === 1 ? "" : "s"} waiting for practice
          </Link>
          <ul className="mt-1 flex flex-col gap-1 text-muted-foreground">
            {d.questions_to_practice.map((q) => (
              <li key={q.question_id} className="truncate">
                <Link href={`/questions/${q.question_id}`} className="hover:underline">
                  {q.text}
                </Link>{" "}
                <span className="text-xs">({PRACTICE_STATUS[q.practice_status].label.toLowerCase()})</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

function Welcome() {
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 py-6">
      <h1 className="text-2xl font-semibold tracking-tight">Welcome to CareerLens</h1>
      <p className="text-muted-foreground">
        CareerLens connects a job&apos;s requirements, the evidence in your CV, your preparation and what happens in each
        recruitment round, so each application teaches you something for the next.
      </p>
      <ol className="flex list-decimal flex-col gap-2 pl-5 text-sm">
        <li>
          <Link href="/cvs" className="font-medium underline underline-offset-4">Upload your CV</Link> and check how it was read.
        </li>
        <li>
          <Link href="/applications/new" className="font-medium underline underline-offset-4">Add an application</Link> with the
          job description, and choose the CV you used.
        </li>
        <li>Analyse its requirements to see what your CV demonstrates, and where.</li>
        <li>Track each round, prepare for it, and write a journal afterwards.</li>
      </ol>
      <div>
        <Link href="/applications/new" className={buttonClass()}>
          Add your first application
        </Link>
      </div>
    </div>
  );
}
