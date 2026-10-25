"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";

import { JournalForm } from "@/components/journals/journal-form";
import { applicationKeys, getApplication } from "@/lib/applications";

export function NewJournal() {
  const { id } = useParams<{ id: string }>();
  const roundId = useSearchParams().get("round");
  const application = useQuery({ queryKey: applicationKeys.detail(id), queryFn: () => getApplication(id) });

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <div className="flex flex-col gap-1">
        <Link href={`/applications/${id}`} className="text-sm text-muted-foreground hover:text-foreground">
          ← {application.data ? `${application.data.position_title}, ${application.data.company_name}` : "Application"}
        </Link>
        <h1 className="text-xl font-semibold tracking-tight">Write a journal</h1>
        <p className="text-sm text-muted-foreground">
          Record what happened while it&apos;s fresh. Patterns across journals show what to practise next.
        </p>
      </div>
      {application.isPending ? (
        <div aria-hidden className="h-64 animate-pulse rounded-xl bg-muted" />
      ) : application.isError ? (
        <p role="alert" className="text-sm text-destructive">
          This application couldn&apos;t be loaded.
        </p>
      ) : (
        <JournalForm application={application.data} initialRoundId={roundId} />
      )}
    </div>
  );
}
