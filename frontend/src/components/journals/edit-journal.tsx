"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";

import { JournalForm } from "@/components/journals/journal-form";
import { applicationKeys, getApplication } from "@/lib/applications";
import { getJournal, journalKeys } from "@/lib/journals";

export function EditJournal() {
  const { id } = useParams<{ id: string }>();
  const journal = useQuery({ queryKey: journalKeys.detail(id), queryFn: () => getJournal(id) });
  const applicationId = journal.data?.application_id;
  const application = useQuery({
    queryKey: applicationKeys.detail(applicationId ?? "none"),
    queryFn: () => getApplication(applicationId!),
    enabled: Boolean(applicationId),
  });

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <div className="flex flex-col gap-1">
        <Link href={`/journals/${id}`} className="text-sm text-muted-foreground hover:text-foreground">
          ← Back to the journal
        </Link>
        <h1 className="text-xl font-semibold tracking-tight">Edit journal</h1>
        <p className="text-sm text-muted-foreground">Add questions from the journal page.</p>
      </div>
      {journal.isError || application.isError ? (
        <p role="alert" className="text-sm text-destructive">
          This journal couldn&apos;t be loaded.
        </p>
      ) : !journal.data || !application.data ? (
        <div aria-hidden className="h-64 animate-pulse rounded-xl bg-muted" />
      ) : (
        <JournalForm key={journal.data.updated_at} application={application.data} journal={journal.data} />
      )}
    </div>
  );
}
