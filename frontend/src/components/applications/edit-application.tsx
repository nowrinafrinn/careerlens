"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";

import { ApplicationForm } from "@/components/applications/application-form";
import { applicationKeys, getApplication } from "@/lib/applications";

export function EditApplication() {
  const { id } = useParams<{ id: string }>();
  const { data, isPending, isError } = useQuery({ queryKey: applicationKeys.detail(id), queryFn: () => getApplication(id) });

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <div className="flex flex-col gap-1">
        <Link href={`/applications/${id}`} className="tap self-start text-sm text-muted-foreground hover:text-foreground">
          ← Back to application
        </Link>
        <h1 className="text-xl font-semibold tracking-tight">Edit details</h1>
        <p className="text-sm text-muted-foreground">
          To change the status, use Change status on the application page, so you can note why.
        </p>
      </div>
      {isPending ? (
        <div aria-hidden className="h-96 animate-pulse rounded-xl bg-muted" />
      ) : isError ? (
        <p role="alert" className="text-sm text-destructive">
          This application couldn&apos;t be loaded.
        </p>
      ) : (
        // key: re-create the form (fresh defaults) if the saved data changes.
        <ApplicationForm key={data.updated_at} application={data} />
      )}
    </div>
  );
}
