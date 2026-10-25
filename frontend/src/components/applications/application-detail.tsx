"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { AnalysisSummary } from "@/components/analysis/analysis-summary";
import { RoundsSection } from "@/components/applications/rounds-section";
import { StatusDialog } from "@/components/applications/status-dialog";
import { ApplicationStatusBadge } from "@/components/applications/status-badge";
import { Timeline } from "@/components/applications/timeline";
import { JournalsSection } from "@/components/journals/journals-section";
import { Button } from "@/components/ui/button";
import { buttonClass } from "@/lib/button-class";
import { ApiError } from "@/lib/api";
import {
  applicationKeys,
  getApplication,
  getTimeline,
  setArchived,
  type ApplicationDetail as Detail,
} from "@/lib/applications";
import { daysUntil, describeDaysUntil, formatDate, formatDateTime } from "@/lib/format";

export function ApplicationDetail() {
  const { id } = useParams<{ id: string }>();
  const detail = useQuery({ queryKey: applicationKeys.detail(id), queryFn: () => getApplication(id) });
  const timeline = useQuery({ queryKey: applicationKeys.timeline(id), queryFn: () => getTimeline(id) });

  if (detail.isPending) return <DetailSkeleton />;
  if (detail.isError) {
    const notFound = detail.error instanceof ApiError && detail.error.status === 404;
    return (
      <div className="flex flex-col items-start gap-3">
        <h1 className="text-xl font-semibold">{notFound ? "Application not found" : "Something went wrong"}</h1>
        <p className="text-sm text-muted-foreground">
          {notFound
            ? "It may have been removed, or the link is wrong."
            : "The application couldn't be loaded. Check that the backend is running, then refresh."}
        </p>
        <Link href="/applications" className={buttonClass({ variant: "outline", size: "sm" })}>
          Back to applications
        </Link>
      </div>
    );
  }

  const application = detail.data;
  return (
    <div className="flex flex-col gap-6">
      <Header application={application} />
      {application.archived_at && <ArchivedBanner application={application} />}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="flex min-w-0 flex-col gap-6">
          <AnalysisSummary application={application} />
          <RoundsSection applicationId={application.id} rounds={application.rounds} />
          <JournalsSection applicationId={application.id} />
          <JobDescription text={application.job_description} applicationId={application.id} />
        </div>

        <aside className="flex min-w-0 flex-col gap-6">
          <Facts application={application} />
          {application.notes && (
            <section aria-labelledby="notes-heading" className="rounded-xl border bg-background p-4">
              <h2 id="notes-heading" className="mb-2 text-sm font-semibold">
                Notes
              </h2>
              <p className="text-sm whitespace-pre-wrap">{application.notes}</p>
            </section>
          )}
          <section aria-labelledby="history-heading" className="rounded-xl border bg-background p-4">
            <h2 id="history-heading" className="mb-3 text-sm font-semibold">
              History
            </h2>
            {timeline.isPending ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : timeline.isError ? (
              <p className="text-sm text-destructive">History couldn&apos;t be loaded.</p>
            ) : (
              <Timeline events={timeline.data} />
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}

function Header({ application }: { application: Detail }) {
  const queryClient = useQueryClient();
  const archive = useMutation({
    mutationFn: () => setArchived(application.id, true),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: applicationKeys.all }),
  });

  return (
    <div className="flex flex-col gap-4">
      <Link href="/applications" className="text-sm text-muted-foreground hover:text-foreground">
        ← Applications
      </Link>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 flex-col gap-1">
          <p className="text-sm text-muted-foreground">{application.company_name}</p>
          <h1 className="text-2xl font-semibold tracking-tight text-balance">{application.position_title}</h1>
          <div className="mt-1">
            <ApplicationStatusBadge status={application.status} />
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href={`/applications/${application.id}/prepare`} className={buttonClass({ size: "sm" })}>
            Prepare
          </Link>
          <StatusDialog application={application} />
          <Link href={`/applications/${application.id}/edit`} className={buttonClass({ variant: "outline", size: "sm" })}>
            Edit details
          </Link>
          {!application.archived_at && (
            <Button
              variant="ghost"
              size="sm"
              className="text-muted-foreground"
              onClick={() => archive.mutate()}
              disabled={archive.isPending}
            >
              Archive
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

function ArchivedBanner({ application }: { application: Detail }) {
  const queryClient = useQueryClient();
  const restore = useMutation({
    mutationFn: () => setArchived(application.id, false),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: applicationKeys.all }),
  });
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-muted px-4 py-3 text-sm">
      <span>
        Archived on {formatDateTime(application.archived_at)}. It&apos;s hidden from your list but nothing was deleted.
      </span>
      <Button variant="outline" size="sm" onClick={() => restore.mutate()} disabled={restore.isPending}>
        Restore
      </Button>
    </div>
  );
}

function Facts({ application }: { application: Detail }) {
  const days = application.deadline ? daysUntil(application.deadline) : null;
  return (
    <section aria-labelledby="facts-heading" className="rounded-xl border bg-background p-4">
      <h2 id="facts-heading" className="sr-only">
        Details
      </h2>
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-2.5 text-sm">
        <dt className="text-muted-foreground">Deadline</dt>
        <dd className="tabular-nums">
          {formatDate(application.deadline)}
          {days !== null && !application.applied_on && (
            <span className={days < 0 ? "text-destructive" : "text-muted-foreground"}> ({describeDaysUntil(days)})</span>
          )}
        </dd>
        <dt className="text-muted-foreground">Applied</dt>
        <dd className="tabular-nums">{application.applied_on ? formatDate(application.applied_on) : "Not yet"}</dd>
        <dt className="text-muted-foreground">CV used</dt>
        <dd className="truncate">
          {application.cv_version ? (
            <Link href={`/cvs/${application.cv_version.id}`} className="text-primary underline underline-offset-4">
              v{application.cv_version.version_number} · {application.cv_version.label}
            </Link>
          ) : (
            <Link href={`/applications/${application.id}/edit`} className="text-muted-foreground underline underline-offset-4">
              Choose a CV
            </Link>
          )}
        </dd>
        <dt className="text-muted-foreground">Source</dt>
        <dd>{application.source ?? "—"}</dd>
        <dt className="text-muted-foreground">Posting</dt>
        <dd className="truncate">
          {application.job_url ? (
            <a
              href={application.job_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary underline underline-offset-4"
            >
              {new URL(application.job_url).hostname}
            </a>
          ) : (
            "—"
          )}
        </dd>
        <dt className="text-muted-foreground">Saved</dt>
        <dd className="tabular-nums">{formatDateTime(application.created_at)}</dd>
      </dl>
    </section>
  );
}

function JobDescription({ text, applicationId }: { text: string | null; applicationId: string }) {
  const [expanded, setExpanded] = useState(false);
  const long = (text?.length ?? 0) > 1200;

  return (
    <section aria-labelledby="jd-heading" className="flex flex-col gap-3">
      <h2 id="jd-heading" className="text-base font-semibold">
        Job description
      </h2>
      {text ? (
        <div className="rounded-xl border bg-background p-4">
          <p className={`text-sm whitespace-pre-wrap ${long && !expanded ? "line-clamp-[16]" : ""}`}>{text}</p>
          {long && (
            <Button variant="link" size="sm" className="mt-2 px-0" onClick={() => setExpanded((value) => !value)}>
              {expanded ? "Show less" : "Show full description"}
            </Button>
          )}
        </div>
      ) : (
        <div className="rounded-xl border border-dashed bg-background px-5 py-6 text-sm text-muted-foreground">
          No job description saved.{" "}
          <Link href={`/applications/${applicationId}/edit`} className="text-foreground underline underline-offset-4">
            Add it
          </Link>{" "}
          so CareerLens can later compare its requirements with your CV.
        </div>
      )}
    </section>
  );
}

function DetailSkeleton() {
  return (
    <div aria-hidden className="flex flex-col gap-4">
      <div className="h-4 w-24 animate-pulse rounded bg-muted" />
      <div className="h-7 w-72 animate-pulse rounded bg-muted" />
      <div className="h-5 w-20 animate-pulse rounded-full bg-muted" />
      <div className="mt-4 h-40 animate-pulse rounded-xl bg-muted" />
    </div>
  );
}
