"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";

import { describedBy, FormField, readApiError, type FieldErrors } from "@/components/form-field";
import { Button } from "@/components/ui/button";
import { buttonClass } from "@/lib/button-class";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import {
  applicationKeys,
  createApplication,
  updateApplication,
  type ApplicationCreate,
  type ApplicationDetail,
  type ApplicationUpdate,
} from "@/lib/applications";
import { APPLICATION_STATUS, APPLICATION_STATUS_ORDER } from "@/lib/labels";

// Text fields edited here. Status is changed on the detail page, where a reason can be recorded.
const TEXT_FIELDS = [
  "company_name",
  "position_title",
  "job_url",
  "source",
  "deadline",
  "applied_on",
  "job_description",
  "notes",
] as const;
type TextField = (typeof TEXT_FIELDS)[number];

function readForm(form: HTMLFormElement): Record<TextField, string | null> {
  const data = new FormData(form);
  const values = {} as Record<TextField, string | null>;
  for (const field of TEXT_FIELDS) {
    const raw = String(data.get(field) ?? "");
    // Long text keeps its inner formatting; empty means "not set".
    values[field] = raw.trim() === "" ? null : field === "job_description" || field === "notes" ? raw : raw.trim();
  }
  return values;
}

export function ApplicationForm({ application }: { application?: ApplicationDetail }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const formRef = useRef<HTMLFormElement>(null);
  const [errors, setErrors] = useState<{ fields: FieldErrors; form: string | null }>({ fields: {}, form: null });
  const editing = Boolean(application);

  const mutation = useMutation({
    mutationFn: async (form: HTMLFormElement) => {
      const values = readForm(form);
      if (!application) {
        const status = String(new FormData(form).get("status")) as ApplicationCreate["status"];
        return createApplication({ ...(values as ApplicationCreate), status });
      }
      // Send only what changed, so the history records real changes only.
      const changes: ApplicationUpdate = {};
      for (const field of TEXT_FIELDS) {
        if ((application[field] ?? null) !== values[field]) {
          (changes as Record<string, string | null>)[field] = values[field];
        }
      }
      return Object.keys(changes).length ? updateApplication(application.id, changes) : application;
    },
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: applicationKeys.all });
      formRef.current?.reset(); // this page stays mounted (hidden) after navigating away
      router.push(`/applications/${saved.id}`);
    },
    onError: (error) => setErrors(readApiError(error)),
  });

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrors({ fields: {}, form: null });
    mutation.mutate(event.currentTarget);
  }

  const err = errors.fields;

  return (
    <form ref={formRef} onSubmit={onSubmit} className="flex flex-col gap-6" noValidate={false}>
      <section className="grid gap-5 rounded-xl border bg-background p-5 sm:grid-cols-2 sm:p-6">
        <h2 className="text-sm font-semibold sm:col-span-2">Position</h2>
        <FormField id="position_title" label="Position title" error={err.position_title}>
          <Input
            id="position_title"
            name="position_title"
            required
            maxLength={200}
            defaultValue={application?.position_title}
            autoFocus={!editing}
            {...describedBy("position_title", err.position_title)}
          />
        </FormField>
        <FormField id="company_name" label="Company" error={err.company_name}>
          <Input
            id="company_name"
            name="company_name"
            required
            maxLength={200}
            defaultValue={application?.company_name}
            {...describedBy("company_name", err.company_name)}
          />
        </FormField>
        <FormField
          id="job_url"
          label="Job posting link"
          optional
          error={err.job_url}
          hint="Must start with http:// or https://"
          className="sm:col-span-2"
        >
          <Input
            id="job_url"
            name="job_url"
            type="url"
            inputMode="url"
            placeholder="https://"
            defaultValue={application?.job_url ?? ""}
            {...describedBy("job_url", err.job_url, true)}
          />
        </FormField>
        <FormField id="source" label="Where you found it" optional hint="LinkedIn, company site, referral…" error={err.source}>
          <Input
            id="source"
            name="source"
            maxLength={100}
            defaultValue={application?.source ?? ""}
            {...describedBy("source", err.source, true)}
          />
        </FormField>
        {!editing && (
          <FormField id="status" label="Status">
            <NativeSelect id="status" name="status" defaultValue="interested">
              {APPLICATION_STATUS_ORDER.map((value) => (
                <option key={value} value={value}>
                  {APPLICATION_STATUS[value].label}
                </option>
              ))}
            </NativeSelect>
          </FormField>
        )}
        <FormField id="deadline" label="Application deadline" optional error={err.deadline}>
          <Input
            id="deadline"
            name="deadline"
            type="date"
            defaultValue={application?.deadline ?? ""}
            {...describedBy("deadline", err.deadline)}
          />
        </FormField>
        <FormField
          id="applied_on"
          label="Date applied"
          optional
          hint="Filled in automatically when the status becomes Applied."
          error={err.applied_on}
        >
          <Input
            id="applied_on"
            name="applied_on"
            type="date"
            defaultValue={application?.applied_on ?? ""}
            {...describedBy("applied_on", err.applied_on, true)}
          />
        </FormField>
      </section>

      <section className="flex flex-col gap-5 rounded-xl border bg-background p-5 sm:p-6">
        <h2 className="text-sm font-semibold">Details</h2>
        <FormField
          id="job_description"
          label="Job description"
          optional
          hint="Paste the full posting. A later milestone extracts its requirements and compares them with your CV."
          error={err.job_description}
        >
          <Textarea
            id="job_description"
            name="job_description"
            rows={10}
            maxLength={100_000}
            defaultValue={application?.job_description ?? ""}
            className="min-h-40 font-normal"
            {...describedBy("job_description", err.job_description, true)}
          />
        </FormField>
        <FormField id="notes" label="Notes" optional hint="Your own observations. Only you can see them." error={err.notes}>
          <Textarea
            id="notes"
            name="notes"
            rows={4}
            maxLength={20_000}
            defaultValue={application?.notes ?? ""}
            {...describedBy("notes", err.notes, true)}
          />
        </FormField>
      </section>

      {errors.form && (
        <p role="alert" className="text-sm text-destructive">
          {errors.form}
        </p>
      )}

      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <Link
          href={application ? `/applications/${application.id}` : "/applications"}
          className={buttonClass({ variant: "outline" })}
        >
          Cancel
        </Link>
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? "Saving…" : editing ? "Save changes" : "Save application"}
        </Button>
      </div>
    </form>
  );
}
