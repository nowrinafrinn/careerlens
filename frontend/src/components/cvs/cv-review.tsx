"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useState, type FormEvent } from "react";

import { Pill } from "@/components/applications/status-badge";
import { FormField } from "@/components/form-field";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { ApiError } from "@/lib/api";
import { applicationKeys } from "@/lib/applications";
import { buttonClass } from "@/lib/button-class";
import {
  cvKeys,
  deleteCV,
  formatFileSize,
  getCV,
  originalFileUrl,
  updateCV,
  updateSection,
  type CVDetail,
  type CVSection,
  type SectionType,
} from "@/lib/cvs";
import { formatDateTime } from "@/lib/format";
import { PARSE_STATUS, SECTION_TYPE } from "@/lib/labels";
import { useCloseOnHide } from "@/lib/use-close-on-hide";

export function CVReview() {
  const { id } = useParams<{ id: string }>();
  const { data: cv, isPending, isError, error } = useQuery({ queryKey: cvKeys.detail(id), queryFn: () => getCV(id) });

  if (isPending) return <div aria-hidden className="h-64 animate-pulse rounded-xl bg-muted" />;
  if (isError) {
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <div className="flex flex-col items-start gap-3">
        <h1 className="text-xl font-semibold">{notFound ? "CV not found" : "Something went wrong"}</h1>
        <Link href="/cvs" className={buttonClass({ variant: "outline", size: "sm" })}>
          Back to CVs
        </Link>
      </div>
    );
  }

  const status = PARSE_STATUS[cv.parse_status];
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4">
        <Link href="/cvs" className="text-sm text-muted-foreground hover:text-foreground">
          ← CVs
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex min-w-0 flex-col gap-1">
            <p className="text-sm text-muted-foreground tabular-nums">Version {cv.version_number}</p>
            <h1 className="text-2xl font-semibold tracking-tight text-balance">{cv.label}</h1>
            <p className="text-sm text-muted-foreground">
              {cv.original_filename} · {formatFileSize(cv.size_bytes)} · uploaded {formatDateTime(cv.created_at)} ·{" "}
              {cv.application_count === 0
                ? "not used by any application"
                : `used by ${cv.application_count} application${cv.application_count === 1 ? "" : "s"}`}
            </p>
            <div className="mt-1 flex flex-wrap gap-1.5">
              <Pill tone={status.tone}>{status.label}</Pill>
              {cv.is_confirmed && <Pill tone="neutral">Reviewed by you</Pill>}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <ConfirmButton cv={cv} />
            <a href={originalFileUrl(cv.id)} className={buttonClass({ variant: "outline", size: "sm" })}>
              Download original
            </a>
            <RenameButton cv={cv} />
            <DeleteButton cv={cv} />
          </div>
        </div>
      </div>

      <div className="rounded-xl border bg-background p-4 text-sm">
        <p>
          <span className="font-medium">{status.description}</span> This is what CareerLens could read from your file.
          If a block is in the wrong section, change its type. Your original file is never modified.
        </p>
        {cv.parse_warnings.length > 0 && (
          <ul className="mt-3 flex list-disc flex-col gap-1 pl-5 text-muted-foreground">
            {cv.parse_warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        )}
      </div>

      {cv.sections.length === 0 ? (
        <p className="text-sm text-muted-foreground">No text was found in this file.</p>
      ) : (
        <ol className="flex flex-col gap-4">
          {cv.sections.map((section) => (
            <SectionCard key={section.id} cvId={cv.id} section={section} />
          ))}
        </ol>
      )}
    </div>
  );
}

function SectionCard({ cvId, section }: { cvId: string; section: CVSection }) {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: (type: SectionType) => updateSection(cvId, section.id, type),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: cvKeys.all });
      // Analyses using this CV may now be out of date.
      queryClient.invalidateQueries({ queryKey: applicationKeys.all });
    },
  });
  const selectId = `section-type-${section.id}`;
  const unrecognized = section.section_type === "unrecognized";

  return (
    <li className={`rounded-xl border bg-background p-4 ${unrecognized ? "border-amber-300 dark:border-amber-800" : ""}`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">{section.heading_text ? "Heading in your CV" : "No heading"}</p>
          <h2 className="font-medium">{section.heading_text ?? SECTION_TYPE[section.section_type]}</h2>
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor={selectId} className="text-sm text-muted-foreground">
            Section type
          </label>
          <NativeSelect
            id={selectId}
            value={section.section_type}
            disabled={mutation.isPending}
            onChange={(event) => mutation.mutate(event.target.value as SectionType)}
            className="w-auto"
          >
            {Object.entries(SECTION_TYPE).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </NativeSelect>
          {section.user_corrected && <Pill tone="info">Set by you</Pill>}
        </div>
      </div>
      {mutation.isError && (
        <p role="alert" className="mt-2 text-sm text-destructive">
          The section type couldn&apos;t be saved. Try again.
        </p>
      )}
      {section.passages.length > 0 && (
        <ul className="mt-3 flex flex-col gap-1.5 border-l pl-4 text-sm">
          {section.passages.map((passage) => (
            <li key={passage.id} className="whitespace-pre-line">
              {passage.text}
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

function ConfirmButton({ cv }: { cv: CVDetail }) {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => updateCV(cv.id, { is_confirmed: !cv.is_confirmed }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: cvKeys.all }),
  });
  return (
    <Button size="sm" variant={cv.is_confirmed ? "outline" : "default"} onClick={() => mutation.mutate()} disabled={mutation.isPending}>
      {cv.is_confirmed ? "Mark as not reviewed" : "Mark as reviewed"}
    </Button>
  );
}

function RenameButton({ cv }: { cv: CVDetail }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  useCloseOnHide(useCallback(() => setOpen(false), []));
  const mutation = useMutation({
    mutationFn: (label: string) => updateCV(cv.id, { label }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: cvKeys.all });
      queryClient.invalidateQueries({ queryKey: applicationKeys.all });
      setOpen(false);
    },
  });

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const label = String(new FormData(event.currentTarget).get("label") ?? "").trim();
    if (label) mutation.mutate(label);
  }

  return (
    <>
      <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
        Rename
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <form onSubmit={onSubmit} className="grid gap-4">
            <DialogHeader>
              <DialogTitle>Rename this version</DialogTitle>
              <DialogDescription>A name that tells versions apart, like &quot;Backend, Oct 2026&quot;.</DialogDescription>
            </DialogHeader>
            <FormField id="cv-rename" label="Name">
              <Input id="cv-rename" name="label" defaultValue={cv.label} maxLength={100} required />
            </FormField>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={mutation.isPending}>
                Save name
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}

function DeleteButton({ cv }: { cv: CVDetail }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  useCloseOnHide(useCallback(() => setOpen(false), []));
  const mutation = useMutation({
    mutationFn: () => deleteCV(cv.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: cvKeys.all });
      router.push("/cvs");
    },
  });
  const inUse = cv.application_count > 0;

  return (
    <>
      <Button variant="ghost" size="sm" className="text-muted-foreground" onClick={() => setOpen(true)}>
        Delete
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{inUse ? "This CV is in use" : `Delete ${cv.label}?`}</DialogTitle>
            <DialogDescription>
              {inUse
                ? `It's linked to ${cv.application_count} application${cv.application_count === 1 ? "" : "s"}. Choose a different CV for them first, so their records stay accurate.`
                : "The uploaded file and everything read from it will be permanently deleted."}
            </DialogDescription>
          </DialogHeader>
          {mutation.isError && (
            <p role="alert" className="text-sm text-destructive">
              {mutation.error instanceof ApiError ? mutation.error.message : "The CV couldn't be deleted."}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              {inUse ? "Close" : "Keep it"}
            </Button>
            {!inUse && (
              <Button variant="destructive" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
                {mutation.isPending ? "Deleting…" : "Delete permanently"}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
