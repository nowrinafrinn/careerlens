"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState, type ReactNode } from "react";

import { InsightCard } from "@/components/dashboard/insight-card";
import { buttonClass } from "@/lib/button-class";
import { dashboardKeys, getDashboard, getInsights, localToday, pickNextStep, type Dashboard, type NextStep } from "@/lib/dashboard";
import { daysUntil, describeDaysUntil, formatDateTime, formatDayMonth, formatLocalDate, formatLongDate } from "@/lib/format";
import { APPLICATION_STATUS, APPLICATION_STATUS_ORDER, GAP_STATUS, PRACTICE_STATUS, TASK_STATUS } from "@/lib/labels";
import type { ApplicationStatus } from "@/lib/applications";
import type { GapStatus } from "@/lib/learning";

const CLOSED_STATUSES = new Set<ApplicationStatus>(["offer", "rejected", "withdrawn", "closed_unknown"]);

function Card({ title, action, children, className = "" }: { title: string; action?: ReactNode; children: ReactNode; className?: string }) {
  const id = `card-${title.toLowerCase().replace(/[^a-z]+/g, "-")}`;
  return (
    <section aria-labelledby={id} className={`flex min-w-0 flex-col gap-3 surface rounded-2xl border p-5 ${className}`}>
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

const CardLink = ({ href, children }: { href: string; children: ReactNode }) => (
  <Link href={href} className="tap text-sm text-muted-foreground underline underline-offset-4">
    {children}
  </Link>
);

const Empty = ({ children }: { children: ReactNode }) => <p className="text-sm text-muted-foreground">{children}</p>;

function ProgressBar({ percent, label, thick = false }: { percent: number; label?: string; thick?: boolean }) {
  return (
    <div
      {...(label ? { role: "img", "aria-label": label } : { "aria-hidden": true })}
      className={`${thick ? "h-2" : "h-1.5"} overflow-hidden rounded-full bg-muted`}
    >
      <div className="h-full rounded-full bg-primary" style={{ width: `${percent}%` }} />
    </div>
  );
}

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
  const closedCount = Object.values(d.outcome_counts).reduce((a, b) => a + b, 0);

  if (activeCount + closedCount === 0 && d.top_tasks.length === 0 && d.recent_journals.length === 0) {
    return <GettingStarted d={d} />;
  }

  const next = pickNextStep(d);
  const attentionItems = d.needs_attention.filter((item) => item !== next?.attention);
  const shownInsights = (insights.data?.insights ?? []).slice(0, 3);
  const roundsThisWeek = d.upcoming_rounds.filter((r) => daysUntil(formatLocalDate(r.scheduled_at)) <= 7).length;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h1 className="text-2xl font-bold tracking-tight">{formatLongDate(d.today)}</h1>
        <p className="text-sm text-muted-foreground">
          {activeCount} active application{activeCount === 1 ? "" : "s"}
          {roundsThisWeek > 0 && ` · ${roundsThisWeek} round${roundsThisWeek === 1 ? "" : "s"} this week`}
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <NextStepCard step={next} className={attentionItems.length > 0 ? "lg:col-span-2" : "lg:col-span-3"} />
        {attentionItems.length > 0 && <NeedsAttention items={attentionItems} />}
      </div>

      <Pipeline d={d} closedCount={closedCount} />

      <div className="grid gap-4 lg:grid-cols-3">
        <Agenda d={d} />
        <CvEvidence d={d} />
        <Skills d={d} />
      </div>

      <Card title="What you are learning from applications" action={<CardLink href="/insights">All insights</CardLink>}>
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
        {d.recent_journals[0] && (
          <p className="border-t pt-3 text-sm text-muted-foreground">
            Latest journal:{" "}
            <Link href={`/journals/${d.recent_journals[0].journal_id}`} className="tap font-medium text-foreground hover:underline">
              {d.recent_journals[0].round_name ?? "Journal"} · {d.recent_journals[0].company_name}
            </Link>{" "}
            · {formatDateTime(d.recent_journals[0].created_at)}
          </p>
        )}
      </Card>
    </div>
  );
}

function NextStepCard({ step, className }: { step: NextStep | null; className: string }) {
  return (
    <section aria-labelledby="next-step" className={`no-lift flex min-w-0 flex-col gap-4 surface rounded-2xl border !border-primary p-6 ${className}`}>
      <h2 id="next-step" className="text-xs font-semibold uppercase tracking-widest text-primary">
        Your next step
      </h2>
      {step ? (
        <>
          <div>
            <p className="text-2xl font-bold leading-tight tracking-tight md:text-3xl">{step.title}</p>
            <p className="mt-1.5 text-muted-foreground">{step.detail}</p>
          </div>
          {step.prep && step.prep.total > 0 && (
            <div className="flex flex-col gap-1.5">
              <div className="flex justify-between gap-3 text-sm text-muted-foreground">
                <span>Preparation</span>
                <span className="font-mono">
                  {step.prep.done} of {step.prep.total} tasks done
                </span>
              </div>
              <ProgressBar
                thick
                percent={(step.prep.done / step.prep.total) * 100}
                label={`${step.prep.done} of ${step.prep.total} preparation tasks done`}
              />
            </div>
          )}
          <div>
            <Link href={step.href} className={buttonClass({ size: "lg" })}>
              {step.action}
            </Link>
          </div>
        </>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-2xl font-bold leading-tight tracking-tight">You&apos;re up to date</p>
          <p className="text-muted-foreground">Nothing is waiting on you. Add a role you&apos;re interested in to keep moving.</p>
          <div>
            <Link href="/applications/new" className={buttonClass({ size: "lg" })}>
              Add an application
            </Link>
          </div>
        </div>
      )}
    </section>
  );
}

function NeedsAttention({ items }: { items: Dashboard["needs_attention"] }) {
  return (
    <section aria-labelledby="attention-heading" className="flex min-w-0 flex-col gap-3 rounded-2xl border border-amber-300 bg-amber-50/60 p-5 dark:border-amber-800 dark:bg-amber-950/40">
      <h2 id="attention-heading" className="text-sm font-semibold">
        Needs attention <span className="font-normal text-muted-foreground tabular-nums">({items.length})</span>
      </h2>
      <ul className="flex flex-col gap-2.5 text-sm">
        {items.map((item, index) => {
          const label = item.title ?? ([item.round_name, item.company_name].filter(Boolean).join(" · ") || item.position_title);
          return (
            <li key={`${item.kind}-${index}`}>
              {item.application_id ? (
                <Link href={`/applications/${item.application_id}`} className="tap block font-medium hover:underline">
                  {label}
                </Link>
              ) : (
                <span className="block font-medium">{label}</span>
              )}
              <span className="block text-muted-foreground">{item.message}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function Pipeline({ d, closedCount }: { d: Dashboard; closedCount: number }) {
  const stages = APPLICATION_STATUS_ORDER.filter((s) => !CLOSED_STATUSES.has(s) || s === "offer");
  const count = (s: ApplicationStatus) => (s === "offer" ? d.outcome_counts.offer : d.application_counts[s]) ?? 0;
  const closedWithoutOffer = closedCount - (d.outcome_counts.offer ?? 0);
  return (
    <Card title="Where your applications stand" action={<CardLink href="/applications">All applications</CardLink>}>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
        {stages.map((s: ApplicationStatus) => (
          <Link key={s} href={`/applications?status=${s}`} className="flex flex-col gap-0.5 rounded-xl bg-muted px-3.5 py-3 hover:bg-accent">
            <span className="font-mono text-2xl">{count(s)}</span>
            <span className="text-sm text-muted-foreground">{APPLICATION_STATUS[s].label}</span>
          </Link>
        ))}
      </div>
      {closedWithoutOffer > 0 && <p className="text-sm text-muted-foreground">{closedWithoutOffer} closed without an offer</p>}
    </Card>
  );
}

function Agenda({ d }: { d: Dashboard }) {
  const entries = [
    ...d.upcoming_rounds.map((r) => ({
      key: `round-${r.round_id}`,
      date: formatLocalDate(r.scheduled_at),
      title: r.round_name,
      detail: `${r.company_name}${r.prep_total > 0 ? ` · prep ${r.prep_done}/${r.prep_total}` : ""}`,
      href: `/applications/${r.application_id}`,
    })),
    ...d.upcoming_deadlines.map((a) => ({
      key: `deadline-${a.application_id}`,
      date: a.date,
      title: `Apply: ${a.position_title}`,
      detail: `${a.company_name} · deadline ${describeDaysUntil(daysUntil(a.date))}`,
      href: `/applications/${a.application_id}`,
    })),
    ...d.follow_ups.map((f) => ({
      key: `follow-${f.round_id}`,
      date: f.date,
      title: "Follow up",
      detail: `${f.round_name} · ${f.company_name}`,
      href: `/applications/${f.application_id}`,
    })),
  ]
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(0, 6);
  return (
    <Card title="Next 14 days">
      {entries.length === 0 ? (
        <Empty>No rounds, deadlines or follow-ups in the next two weeks.</Empty>
      ) : (
        <ul className="flex flex-col gap-2.5 text-sm">
          {entries.map((e) => (
            <li key={e.key} className="grid grid-cols-[3.5rem_minmax(0,1fr)] gap-3">
              <span className="font-mono text-muted-foreground">{formatDayMonth(e.date)}</span>
              <Link href={e.href} className="tap min-w-0 hover:underline">
                <span className="block font-medium">{e.title}</span>
                <span className="block text-muted-foreground">{e.detail}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function CvEvidence({ d }: { d: Dashboard }) {
  return (
    <Card title="What your CV shows">
      {d.analyses.length === 0 ? (
        <Empty>No analyses yet. Open an application with a job description and a CV to run one.</Empty>
      ) : (
        <ul className="flex flex-col gap-3.5 text-sm">
          {d.analyses.slice(0, 4).map((a) => (
            <li key={a.analysis_id}>
              <Link href={`/applications/${a.application_id}/analysis`} className="tap flex flex-col gap-1">
                <span className="flex justify-between gap-2">
                  <span className="min-w-0 font-medium">{a.position_title}</span>
                  {a.required_total > 0 && (
                    <span className="font-mono text-muted-foreground">
                      {a.demonstrated}/{a.required_total}
                    </span>
                  )}
                </span>
                {a.required_total > 0 && <ProgressBar percent={(a.demonstrated / a.required_total) * 100} />}
                <span className="text-muted-foreground">
                  {a.company_name}
                  {a.required_total === 0 && " · no required lines"}
                  {a.needs_your_input > 0 && ` · ${a.needs_your_input} need your input`}
                  {a.is_stale && " · out of date"}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function Skills({ d }: { d: Dashboard }) {
  const gapStatuses = (["open", "improving", "resolved"] as GapStatus[]).filter((s) => d.gap_counts[s]);
  const latest = d.recent_reassessments[0];
  return (
    <Card title="Skills to build" action={<CardLink href="/learning">Learning plan</CardLink>}>
      {gapStatuses.length > 0 && (
        <p className="text-sm text-muted-foreground">
          {gapStatuses.map((s) => `${d.gap_counts[s]} ${GAP_STATUS[s].label.toLowerCase()}`).join(" · ")}
        </p>
      )}
      {d.top_tasks.length === 0 ? (
        <Empty>No open tasks.</Empty>
      ) : (
        <ul className="flex flex-col gap-2.5 text-sm">
          {d.top_tasks.slice(0, 3).map((t) => {
            const href = t.skill_gap_id
              ? `/learning/${t.skill_gap_id}`
              : t.application_id
                ? `/applications/${t.application_id}/prepare${t.round_id ? `?round=${t.round_id}` : ""}`
                : null;
            const name = <span className="block font-medium">{t.title}</span>;
            return (
              <li key={t.task_id}>
                {href ? (
                  <Link href={href} className="tap block hover:underline">
                    {name}
                  </Link>
                ) : (
                  name
                )}
                <span className="block text-muted-foreground">
                  {t.kind === "preparation" ? "Prep" : "Learning"} · {TASK_STATUS[t.status].label}
                  {t.due_date && ` · due ${formatDayMonth(t.due_date)}`}
                </span>
              </li>
            );
          })}
        </ul>
      )}
      {latest && (
        <p className="text-sm text-muted-foreground">
          Latest progress: {latest.skill_name} {GAP_STATUS[latest.previous_status].label.toLowerCase()} → {GAP_STATUS[latest.new_status].label.toLowerCase()}
        </p>
      )}
      {d.questions_to_practice_total > 0 && (
        <div className="mt-auto border-t pt-3 text-sm">
          <Link href="/questions?practice_status=to_practice" className="tap font-medium hover:underline">
            {d.questions_to_practice_total} question{d.questions_to_practice_total === 1 ? "" : "s"} waiting for practice
          </Link>
          {d.questions_to_practice[0] && (
            <p className="mt-1 truncate text-muted-foreground">
              {d.questions_to_practice[0].text} ({PRACTICE_STATUS[d.questions_to_practice[0].practice_status].label.toLowerCase()})
            </p>
          )}
        </div>
      )}
    </Card>
  );
}

function GettingStarted({ d }: { d: Dashboard }) {
  const cv = d.latest_cv;
  const steps = [
    { title: "Upload your CV", detail: cv ? "Done" : "PDF or DOCX, read into sections you can check" },
    { title: "Add an application", detail: "With the job description and the CV you used" },
    { title: "Analyse the requirements", detail: "See what your CV shows, and where" },
    { title: "Track and reflect", detail: "Prepare for each round, then write a journal" },
  ];
  const current = cv ? 1 : 0;
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h1 className="text-2xl font-bold tracking-tight">{formatLongDate(d.today)}</h1>
        <p className="text-sm text-muted-foreground">Step {current + 1} of {steps.length}</p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <section aria-labelledby="next-step" className={`no-lift flex min-w-0 flex-col gap-4 surface rounded-2xl border !border-primary p-6 ${cv ? "lg:col-span-2" : "lg:col-span-3"}`}>
          <h2 id="next-step" className="text-xs font-semibold uppercase tracking-widest text-primary">
            Your next step
          </h2>
          <div>
            <p className="text-2xl font-bold leading-tight tracking-tight md:text-3xl">
              {cv ? "Add the job you want to apply to" : "Upload your CV"}
            </p>
            <p className="mt-1.5 max-w-prose text-muted-foreground">
              {cv
                ? "Paste its job description. CareerLens pulls out the requirements and shows which ones your CV demonstrates."
                : "CareerLens reads it into sections you can check. Everything it says about you is traced back to this text."}
            </p>
          </div>
          <div>
            <Link href={cv ? "/applications/new" : "/cvs"} className={buttonClass({ size: "lg" })}>
              {cv ? "Add an application" : "Upload a CV"}
            </Link>
          </div>
        </section>

        {cv && (
          <Card title="Your CV">
            <p className="text-sm font-medium">
              {cv.label} · version {cv.version_number}
            </p>
            <p className="text-sm text-muted-foreground">
              Read into {cv.section_count} section{cv.section_count === 1 ? "" : "s"}.
              {!cv.is_confirmed && " Check them before your first analysis, so evidence is matched correctly."}
            </p>
            <div className="mt-auto">
              <CardLink href={`/cvs/${cv.cv_version_id}`}>Review how it was read</CardLink>
            </div>
          </Card>
        )}
      </div>

      <Card title="How CareerLens gets useful">
        <ol className="grid gap-4 md:grid-cols-4">
          {steps.map((step, index) => (
            <li key={step.title} className="flex flex-col gap-1 text-sm">
              <span
                className={`flex size-7 items-center justify-center rounded-full font-mono ${
                  index < current ? "bg-primary text-primary-foreground" : index === current ? "bg-primary/20 text-primary" : "bg-muted text-muted-foreground"
                }`}
              >
                {index < current ? "✓" : index + 1}
              </span>
              <span className="font-medium">{step.title}</span>
              <span className="text-muted-foreground">{step.detail}</span>
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
}
