"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { ApplicationStatusBadge } from "@/components/applications/status-badge";
import { buttonClass } from "@/lib/button-class";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { applicationKeys, listApplications, type Application, type ApplicationStatus } from "@/lib/applications";
import { daysUntil, describeDaysUntil, formatDate } from "@/lib/format";
import { APPLICATION_STATUS, APPLICATION_STATUS_ORDER } from "@/lib/labels";

const PAGE_SIZE = 20;
const CLOSED: ApplicationStatus[] = ["offer", "rejected", "withdrawn", "closed_unknown"];

export function ApplicationsList() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // The URL is the source of truth for filters.
  const status = (searchParams.get("status") as ApplicationStatus | null) ?? undefined;
  const q = searchParams.get("q") ?? "";
  const includeArchived = searchParams.get("archived") === "1";
  const page = Math.max(1, Number(searchParams.get("page")) || 1);

  const params = { status, q: q || undefined, includeArchived, limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE };
  const { data, isPending, isError, isFetching } = useQuery({
    queryKey: applicationKeys.list(params),
    queryFn: () => listApplications(params),
    placeholderData: keepPreviousData, // keep showing the old page while the next one loads
  });

  function setParam(updates: Record<string, string | null>) {
    const next = new URLSearchParams(searchParams);
    for (const [key, value] of Object.entries(updates)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    if (!("page" in updates)) next.delete("page"); // a new filter starts at page 1
    const query = next.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }

  // Search box: type freely, update the URL 300 ms after typing stops.
  const [searchText, setSearchText] = useState(q);
  // If the URL's q changes from elsewhere (Clear filters, back button), follow it.
  const [syncedQ, setSyncedQ] = useState(q);
  if (q !== syncedQ) {
    setSyncedQ(q);
    setSearchText(q);
  }
  useEffect(() => {
    if (searchText.trim() === q) return;
    const timer = setTimeout(() => setParam({ q: searchText.trim() || null }), 300);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only react to typing
  }, [searchText]);

  const total = data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const filtered = Boolean(status || q || includeArchived);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-xl font-semibold tracking-tight">Applications</h1>
          <p className="text-sm text-muted-foreground">
            Positions you are watching, applying to, or interviewing for.
          </p>
        </div>
        <Link href="/applications/new" className={buttonClass()}>
          Add application
        </Link>
      </div>

      <div className="flex flex-wrap items-center gap-3" role="search">
        <Input
          type="search"
          value={searchText}
          onChange={(event) => setSearchText(event.target.value)}
          placeholder="Search company or position"
          aria-label="Search company or position"
          className="w-full sm:w-72"
          maxLength={100}
        />
        <NativeSelect
          aria-label="Filter by status"
          value={status ?? ""}
          onChange={(event) => setParam({ status: event.target.value || null })}
          className="w-auto"
        >
          <option value="">All statuses</option>
          {APPLICATION_STATUS_ORDER.map((value) => (
            <option key={value} value={value}>
              {APPLICATION_STATUS[value].label}
            </option>
          ))}
        </NativeSelect>
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={includeArchived}
            onChange={(event) => setParam({ archived: event.target.checked ? "1" : null })}
            className="size-4 accent-primary"
          />
          Show archived
        </label>
        <span className="ml-auto text-sm text-muted-foreground tabular-nums" aria-live="polite">
          {data ? `${total} ${total === 1 ? "application" : "applications"}` : ""}
        </span>
      </div>

      {isPending ? (
        <ListSkeleton />
      ) : isError ? (
        <p role="alert" className="rounded-lg border bg-background p-6 text-sm text-destructive">
          Applications couldn&apos;t be loaded. Check that the backend is running, then refresh.
        </p>
      ) : data.items.length === 0 ? (
        <EmptyState filtered={filtered} />
      ) : (
        <ul
          className={`divide-y overflow-hidden rounded-xl border bg-background transition-opacity ${isFetching ? "opacity-70" : ""}`}
        >
          {data.items.map((application) => (
            <ApplicationRow key={application.id} application={application} />
          ))}
        </ul>
      )}

      {pageCount > 1 && (
        <nav aria-label="Pagination" className="flex items-center justify-between text-sm">
          <button
            type="button"
            className={buttonClass({ variant: "outline", size: "sm" })}
            disabled={page <= 1}
            onClick={() => setParam({ page: String(page - 1) })}
          >
            Previous
          </button>
          <span className="text-muted-foreground tabular-nums">
            Page {page} of {pageCount}
          </span>
          <button
            type="button"
            className={buttonClass({ variant: "outline", size: "sm" })}
            disabled={page >= pageCount}
            onClick={() => setParam({ page: String(page + 1) })}
          >
            Next
          </button>
        </nav>
      )}
    </div>
  );
}

function ApplicationRow({ application }: { application: Application }) {
  const closed = CLOSED.includes(application.status);
  const deadlineDays = application.deadline ? daysUntil(application.deadline) : null;
  const deadlineSoon = !closed && deadlineDays !== null && deadlineDays >= 0 && deadlineDays <= 7;
  const deadlinePassed = !closed && deadlineDays !== null && deadlineDays < 0 && !application.applied_on;

  return (
    <li>
      <Link
        href={`/applications/${application.id}`}
        className="grid gap-x-6 gap-y-2 px-4 py-3.5 transition-colors hover:bg-muted/50 focus-visible:bg-muted/50 focus-visible:outline-none sm:grid-cols-[minmax(0,1fr)_auto_11rem]"
      >
        <div className="min-w-0">
          <p className="truncate font-medium">{application.position_title}</p>
          <p className="truncate text-sm text-muted-foreground">
            {application.company_name}
            {application.archived_at && " · Archived"}
          </p>
        </div>
        <div className="flex items-center">
          <ApplicationStatusBadge status={application.status} />
        </div>
        <div className="text-sm whitespace-nowrap tabular-nums sm:text-right">
          {application.deadline ? (
            <>
              <p className="text-muted-foreground">Deadline {formatDate(application.deadline)}</p>
              {(deadlineSoon || deadlinePassed) && deadlineDays !== null && (
                <p className={deadlinePassed ? "text-destructive" : "text-amber-700 dark:text-amber-400"}>
                  {deadlinePassed ? "Passed " : "Due "}
                  {describeDaysUntil(deadlineDays)}
                </p>
              )}
            </>
          ) : application.applied_on ? (
            <p className="text-muted-foreground">Applied {formatDate(application.applied_on)}</p>
          ) : (
            <p className="text-muted-foreground">No deadline</p>
          )}
        </div>
      </Link>
    </li>
  );
}

function EmptyState({ filtered }: { filtered: boolean }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed bg-background px-6 py-14 text-center">
      {filtered ? (
        <>
          <p className="font-medium">No applications match these filters</p>
          <p className="max-w-sm text-sm text-muted-foreground">Try a different search or status, or clear the filters.</p>
          <Link href="/applications" className={buttonClass({ variant: "outline", size: "sm" })}>
            Clear filters
          </Link>
        </>
      ) : (
        <>
          <p className="font-medium">No applications yet</p>
          <p className="max-w-sm text-sm text-muted-foreground">
            Save a position you&apos;re interested in. You can add the job description, track each recruitment round
            and keep a history of every change.
          </p>
          <Link href="/applications/new" className={buttonClass({ size: "sm" })}>
            Add your first application
          </Link>
        </>
      )}
    </div>
  );
}

function ListSkeleton() {
  return (
    <ul aria-hidden className="divide-y overflow-hidden rounded-xl border bg-background">
      {Array.from({ length: 4 }, (_, i) => (
        <li key={i} className="flex items-center justify-between gap-6 px-4 py-4">
          <div className="flex flex-col gap-2">
            <div className="h-4 w-48 animate-pulse rounded bg-muted" />
            <div className="h-3 w-28 animate-pulse rounded bg-muted" />
          </div>
          <div className="h-5 w-20 animate-pulse rounded-full bg-muted" />
        </li>
      ))}
    </ul>
  );
}
