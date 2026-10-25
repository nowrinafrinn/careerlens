"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";

import { Pill } from "@/components/applications/status-badge";
import { FormField } from "@/components/form-field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { cvKeys, formatFileSize, listCVs, MAX_CV_BYTES, uploadCV, type CVSummary } from "@/lib/cvs";
import { formatDateTime } from "@/lib/format";
import { PARSE_STATUS } from "@/lib/labels";

export function CVList() {
  const { data, isPending, isError } = useQuery({ queryKey: cvKeys.list(), queryFn: listCVs });

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold tracking-tight">CVs</h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Each upload becomes a numbered version. Applications point at the version you sent, so a tailored CV for
          one job doesn&apos;t change what another job used.
        </p>
      </div>

      <UploadCard />

      <section aria-labelledby="versions-heading" className="flex flex-col gap-3">
        <h2 id="versions-heading" className="text-base font-semibold">
          Your versions
        </h2>
        {isPending ? (
          <div aria-hidden className="h-24 animate-pulse rounded-xl bg-muted" />
        ) : isError ? (
          <p role="alert" className="text-sm text-destructive">
            CVs couldn&apos;t be loaded. Check that the backend is running, then refresh.
          </p>
        ) : data.length === 0 ? (
          <p className="rounded-xl border border-dashed bg-background px-5 py-8 text-sm text-muted-foreground">
            No CVs yet. Upload one above to see what CareerLens can read from it.
          </p>
        ) : (
          <ul className="divide-y overflow-hidden rounded-xl border bg-background">
            {data.map((cv) => (
              <CVRow key={cv.id} cv={cv} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function CVRow({ cv }: { cv: CVSummary }) {
  const status = PARSE_STATUS[cv.parse_status];
  return (
    <li>
      <Link
        href={`/cvs/${cv.id}`}
        className="grid gap-x-6 gap-y-2 px-4 py-3.5 transition-colors hover:bg-muted/50 focus-visible:bg-muted/50 focus-visible:outline-none sm:grid-cols-[minmax(0,1fr)_auto_auto] sm:items-center"
      >
        <div className="min-w-0">
          <p className="truncate font-medium">
            <span className="text-muted-foreground tabular-nums">v{cv.version_number}</span> {cv.label}
          </p>
          <p className="truncate text-sm text-muted-foreground">
            {cv.original_filename} · {formatFileSize(cv.size_bytes)} · {formatDateTime(cv.created_at)}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Pill tone={status.tone}>{status.label}</Pill>
          {cv.is_confirmed && <Pill tone="neutral">Reviewed</Pill>}
        </div>
        <p className="text-sm whitespace-nowrap text-muted-foreground tabular-nums">
          {cv.application_count === 0
            ? "Not used yet"
            : `Used by ${cv.application_count} application${cv.application_count === 1 ? "" : "s"}`}
        </p>
      </Link>
    </li>
  );
}

function UploadCard() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const formRef = useRef<HTMLFormElement>(null);
  const [error, setError] = useState<{ message: string; existingId?: string } | null>(null);

  const mutation = useMutation({
    mutationFn: ({ file, label }: { file: File; label?: string }) => uploadCV(file, label),
    onSuccess: (cv) => {
      queryClient.invalidateQueries({ queryKey: cvKeys.all });
      formRef.current?.reset(); // this page stays mounted (hidden) after navigating away
      router.push(`/cvs/${cv.id}`);
    },
    onError: (err) => {
      if (err instanceof ApiError && err.code === "duplicate_cv") {
        const details = err.details as { cv_version_id?: string } | null;
        setError({ message: err.message, existingId: details?.cv_version_id });
      } else {
        setError({ message: err instanceof ApiError ? err.message : "The upload failed. Please try again." });
      }
    },
  });

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const file = data.get("file");
    const label = String(data.get("label") ?? "").trim();
    setError(null);
    if (!(file instanceof File) || file.size === 0) {
      setError({ message: "Choose a PDF or DOCX file first." });
      return;
    }
    if (file.size > MAX_CV_BYTES) {
      setError({ message: "The file is larger than the 5 MB limit." });
      return;
    }
    mutation.mutate({ file, label: label || undefined });
  }

  return (
    <section aria-labelledby="upload-heading" className="rounded-xl border bg-background p-5 sm:p-6">
      <h2 id="upload-heading" className="text-sm font-semibold">
        Upload a CV
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">
        PDF or DOCX, up to 5 MB. The file is stored as-is and only you can see it. CareerLens reads the text and
        splits it into sections for you to check. Nothing is sent to an AI service.
      </p>
      <form ref={formRef} onSubmit={onSubmit} className="mt-4 grid gap-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] sm:items-end">
        <FormField id="cv-file" label="File">
          <Input
            id="cv-file"
            name="file"
            type="file"
            accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            required
          />
        </FormField>
        <FormField id="cv-label" label="Name for this version" optional>
          <Input id="cv-label" name="label" maxLength={100} placeholder="Backend CV, October" />
        </FormField>
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? "Reading file…" : "Upload"}
        </Button>
      </form>
      {error && (
        <p role="alert" className="mt-3 text-sm text-destructive">
          {error.message}{" "}
          {error.existingId && (
            <Link href={`/cvs/${error.existingId}`} className="text-foreground underline underline-offset-4">
              Open it
            </Link>
          )}
        </p>
      )}
    </section>
  );
}
