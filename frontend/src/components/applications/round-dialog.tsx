"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState, type FormEvent, type ReactNode } from "react";

import { describedBy, FormField, readApiError, type FieldErrors } from "@/components/form-field";
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
import { Textarea } from "@/components/ui/textarea";
import {
  applicationKeys,
  createRound,
  updateRound,
  type Round,
  type RoundCreate,
  type RoundResult,
  type RoundStatus,
  type RoundType,
  type RoundUpdate,
} from "@/lib/applications";
import { fromDateTimeLocal, toDateTimeLocal } from "@/lib/format";
import { ROUND_RESULT, ROUND_STATUS, ROUND_TYPE } from "@/lib/labels";
import { useCloseOnHide } from "@/lib/use-close-on-hide";

type Link = { label: string; url: string };

/** "Label | https://…" or just "https://…" per line. */
function parseLinks(text: string): Link[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [first, ...rest] = line.split("|");
      if (rest.length === 0) {
        let label = "Link";
        try {
          label = new URL(first.trim()).hostname;
        } catch {
          // invalid URL: the API reports it
        }
        return { label, url: first.trim() };
      }
      return { label: first.trim() || "Link", url: rest.join("|").trim() };
    });
}

const formatLinks = (links: Link[]) => links.map((link) => `${link.label} | ${link.url}`).join("\n");

type Values = Omit<RoundCreate, "status"> & { status: RoundStatus | null };

function readForm(form: HTMLFormElement): Values {
  const data = new FormData(form);
  const text = (name: string) => String(data.get(name) ?? "").trim();
  return {
    name: text("name"),
    round_type: text("round_type") as RoundType,
    scheduled_at: fromDateTimeLocal(text("scheduled_at")),
    confirmation_deadline: fromDateTimeLocal(text("confirmation_deadline")),
    status: (text("status") || null) as RoundStatus | null,
    result: text("result") as RoundResult,
    follow_up_date: text("follow_up_date") || null,
    links: parseLinks(String(data.get("links") ?? "")),
    notes: text("notes") || null,
  };
}

/** Fields whose value differs from the saved round, ready for PATCH. */
function changedFields(round: Round, values: Values): RoundUpdate {
  const changes: Record<string, unknown> = {};
  const sameMoment = (a: string | null | undefined, b: string | null | undefined) =>
    (a ? new Date(a).getTime() : null) === (b ? new Date(b).getTime() : null);

  if (values.name !== round.name) changes.name = values.name;
  if (values.round_type !== round.round_type) changes.round_type = values.round_type;
  if (!sameMoment(values.scheduled_at, round.scheduled_at)) changes.scheduled_at = values.scheduled_at;
  if (!sameMoment(values.confirmation_deadline, round.confirmation_deadline))
    changes.confirmation_deadline = values.confirmation_deadline;
  if (values.status && values.status !== round.status) changes.status = values.status;
  if (values.result !== round.result) changes.result = values.result;
  if ((values.follow_up_date ?? null) !== (round.follow_up_date ?? null)) changes.follow_up_date = values.follow_up_date;
  if (JSON.stringify(values.links) !== JSON.stringify(round.links)) changes.links = values.links;
  if ((values.notes ?? null) !== (round.notes ?? null)) changes.notes = values.notes;
  return changes as RoundUpdate;
}

type Props = {
  applicationId: string;
  round?: Round; // present = edit mode
  trigger: (open: () => void) => ReactNode;
};

export function RoundDialog({ applicationId, round, trigger }: Props) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [errors, setErrors] = useState<{ fields: FieldErrors; form: string | null }>({ fields: {}, form: null });
  useCloseOnHide(useCallback(() => setOpen(false), []));
  const editing = Boolean(round);

  const mutation = useMutation({
    mutationFn: async ({ values, reason }: { values: Values; reason: string | null }) => {
      if (!round) {
        const { status, ...rest } = values;
        return createRound(applicationId, { ...rest, ...(status ? { status } : {}) });
      }
      const changes = changedFields(round, values);
      if (Object.keys(changes).length === 0) return round;
      return updateRound(round.id, { ...changes, change_reason: reason });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: applicationKeys.all });
      setOpen(false);
    },
    onError: (error) => setErrors(readApiError(error)),
  });

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrors({ fields: {}, form: null });
    const reason = String(new FormData(event.currentTarget).get("change_reason") ?? "").trim();
    mutation.mutate({ values: readForm(event.currentTarget), reason: reason || null });
  }

  function openDialog() {
    setErrors({ fields: {}, form: null });
    setOpen(true);
  }

  const err = errors.fields;

  return (
    <>
      {trigger(openDialog)}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-xl">
          <form onSubmit={onSubmit} className="grid gap-4">
            <DialogHeader>
              <DialogTitle>{editing ? `Edit ${round?.name}` : "Add a recruitment round"}</DialogTitle>
              <DialogDescription>
                {editing
                  ? "Changing the date, status or result keeps the previous value in the history."
                  : "A round is one step of the process: a screening, an assessment, an interview."}
              </DialogDescription>
            </DialogHeader>

            <div className="grid gap-4 sm:grid-cols-2">
              <FormField id="round-name" label="Name" error={err.name}>
                <Input
                  id="round-name"
                  name="name"
                  required
                  maxLength={200}
                  defaultValue={round?.name}
                  placeholder="Technical interview 1"
                  {...describedBy("round-name", err.name)}
                />
              </FormField>
              <FormField id="round-type" label="Type">
                <NativeSelect id="round-type" name="round_type" defaultValue={round?.round_type ?? "technical_interview"}>
                  {Object.entries(ROUND_TYPE).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </NativeSelect>
              </FormField>
              <FormField id="round-scheduled" label="Date and time" optional hint="In your timezone." error={err.scheduled_at}>
                <Input
                  id="round-scheduled"
                  name="scheduled_at"
                  type="datetime-local"
                  defaultValue={toDateTimeLocal(round?.scheduled_at)}
                  {...describedBy("round-scheduled", err.scheduled_at, true)}
                />
              </FormField>
              <FormField
                id="round-confirm"
                label="Confirm or register by"
                optional
                error={err.confirmation_deadline}
              >
                <Input
                  id="round-confirm"
                  name="confirmation_deadline"
                  type="datetime-local"
                  defaultValue={toDateTimeLocal(round?.confirmation_deadline)}
                  {...describedBy("round-confirm", err.confirmation_deadline)}
                />
              </FormField>
              <FormField
                id="round-status"
                label="Status"
                hint={editing ? "Where the round is in time." : "Leave on automatic to set it from the date."}
              >
                <NativeSelect
                  id="round-status"
                  name="status"
                  defaultValue={round?.status ?? ""}
                  aria-describedby="round-status-hint"
                >
                  {!editing && <option value="">Automatic</option>}
                  {Object.entries(ROUND_STATUS).map(([value, meta]) => (
                    <option key={value} value={value}>
                      {meta.label}
                    </option>
                  ))}
                </NativeSelect>
              </FormField>
              <FormField id="round-result" label="Result" hint="How it went. Separate from status.">
                <NativeSelect
                  id="round-result"
                  name="result"
                  defaultValue={round?.result ?? "unknown"}
                  aria-describedby="round-result-hint"
                >
                  {Object.entries(ROUND_RESULT).map(([value, meta]) => (
                    <option key={value} value={value}>
                      {meta.label}
                    </option>
                  ))}
                </NativeSelect>
              </FormField>
              <FormField id="round-follow-up" label="Follow up on" optional error={err.follow_up_date}>
                <Input
                  id="round-follow-up"
                  name="follow_up_date"
                  type="date"
                  defaultValue={round?.follow_up_date ?? ""}
                  {...describedBy("round-follow-up", err.follow_up_date)}
                />
              </FormField>
            </div>

            <FormField
              id="round-links"
              label="Links"
              optional
              hint="One per line, e.g. Meeting link | https://meet.example.com/abc"
              error={err.links}
            >
              <Textarea
                id="round-links"
                name="links"
                rows={2}
                defaultValue={round ? formatLinks(round.links) : ""}
                {...describedBy("round-links", err.links, true)}
              />
            </FormField>
            <FormField id="round-notes" label="Notes" optional error={err.notes}>
              <Textarea
                id="round-notes"
                name="notes"
                rows={3}
                maxLength={20_000}
                defaultValue={round?.notes ?? ""}
                {...describedBy("round-notes", err.notes)}
              />
            </FormField>
            {editing && (
              <FormField
                id="round-reason"
                label="Reason for the change"
                optional
                hint="Saved in the history with any date, status or result change."
              >
                <Input id="round-reason" name="change_reason" maxLength={1000} aria-describedby="round-reason-hint" />
              </FormField>
            )}

            {errors.form && (
              <p role="alert" className="text-sm text-destructive">
                {errors.form}
              </p>
            )}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending ? "Saving…" : editing ? "Save round" : "Add round"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
