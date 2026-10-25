"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useCallback, useState, type FormEvent } from "react";

import { FormField } from "@/components/form-field";
import { RoundDialog } from "@/components/applications/round-dialog";
import { RoundResultBadge, RoundStatusBadge } from "@/components/applications/status-badge";
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
import { applicationKeys, deleteRound, type Round } from "@/lib/applications";
import { buttonClass } from "@/lib/button-class";
import { listPrepTasks, preparationKeys } from "@/lib/preparation";
import { formatDate, formatDateTime } from "@/lib/format";
import { ROUND_TYPE } from "@/lib/labels";
import { useCloseOnHide } from "@/lib/use-close-on-hide";

export function RoundsSection({ applicationId, rounds }: { applicationId: string; rounds: Round[] }) {
  // One request for the whole application; grouped per round for the "Prepare" progress.
  const prepTasks = useQuery({ queryKey: preparationKeys.checklist(applicationId, null), queryFn: () => listPrepTasks(applicationId, null) });
  const progress = (roundId: string) => {
    const tasks = prepTasks.data?.filter((t) => t.recruitment_round_id === roundId) ?? [];
    return { total: tasks.length, done: tasks.filter((t) => t.status === "completed").length };
  };
  return (
    <section aria-labelledby="rounds-heading" className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-4">
        <h2 id="rounds-heading" className="text-base font-semibold">
          Recruitment rounds
        </h2>
        <RoundDialog
          applicationId={applicationId}
          trigger={(open) => (
            <Button size="sm" onClick={open}>
              Add round
            </Button>
          )}
        />
      </div>

      {rounds.length === 0 ? (
        <div className="rounded-xl border border-dashed bg-background px-5 py-8 text-sm text-muted-foreground">
          No rounds yet. Add one when you hear about the next step, such as a CV screening, an online
          assessment or an interview.
        </div>
      ) : (
        <ol className="flex flex-col gap-3">
          {rounds.map((round, index) => (
            <RoundCard key={round.id} applicationId={applicationId} round={round} number={index + 1} prep={progress(round.id)} />
          ))}
        </ol>
      )}
    </section>
  );
}

function RoundCard({
  applicationId,
  round,
  number,
  prep,
}: {
  applicationId: string;
  round: Round;
  number: number;
  prep: { total: number; done: number };
}) {
  return (
    <li className="rounded-xl border bg-background p-4">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">
            Round {number} · {ROUND_TYPE[round.round_type]}
          </p>
          <h3 className="font-medium">{round.name}</h3>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <RoundStatusBadge status={round.status} />
          <RoundResultBadge result={round.result} />
        </div>
      </div>

      <dl className="mt-3 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
        <Detail label="When" value={round.scheduled_at ? formatDateTime(round.scheduled_at) : "Not scheduled"} />
        {round.confirmation_deadline && (
          <Detail label="Confirm by" value={formatDateTime(round.confirmation_deadline)} />
        )}
        {round.follow_up_date && <Detail label="Follow up on" value={formatDate(round.follow_up_date)} />}
        {round.completed_at && <Detail label="Completed" value={formatDateTime(round.completed_at)} />}
      </dl>

      {round.links.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm">
          {round.links.map((link) => (
            <li key={link.url}>
              <a
                href={link.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary underline underline-offset-4"
              >
                {link.label}
              </a>
            </li>
          ))}
        </ul>
      )}

      {round.notes && <p className="mt-3 text-sm whitespace-pre-wrap text-muted-foreground">{round.notes}</p>}

      <div className="mt-4 flex flex-wrap gap-2">
        <Link href={`/applications/${applicationId}/prepare?round=${round.id}`} className={buttonClass({ size: "sm" })}>
          Prepare{prep.total > 0 && <span className="tabular-nums"> · {prep.done}/{prep.total}</span>}
        </Link>
        <Link
          href={`/applications/${applicationId}/journals/new?round=${round.id}`}
          className={buttonClass({ variant: "outline", size: "sm" })}
        >
          Write journal
        </Link>
        <RoundDialog
          applicationId={applicationId}
          round={round}
          trigger={(open) => (
            <Button variant="outline" size="sm" onClick={open}>
              Edit
            </Button>
          )}
        />
        <DeleteRoundButton round={round} />
      </div>
    </li>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="tabular-nums">{value}</dd>
    </div>
  );
}

function DeleteRoundButton({ round }: { round: Round }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  useCloseOnHide(useCallback(() => setOpen(false), []));

  const mutation = useMutation({
    mutationFn: (reason: string | undefined) => deleteRound(round.id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: applicationKeys.all });
      setOpen(false);
    },
  });

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const reason = String(new FormData(event.currentTarget).get("reason") ?? "").trim();
    mutation.mutate(reason || undefined);
  }

  return (
    <>
      <Button variant="ghost" size="sm" className="text-muted-foreground" onClick={() => setOpen(true)}>
        Delete
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <form onSubmit={onSubmit} className="grid gap-4">
            <DialogHeader>
              <DialogTitle>Delete {round.name}?</DialogTitle>
              <DialogDescription>
                Use this for a round added by mistake. If it was cancelled, edit its status to Cancelled instead.
                The round&apos;s history is kept either way.
              </DialogDescription>
            </DialogHeader>
            <FormField id={`delete-reason-${round.id}`} label="Reason" optional>
              <Input id={`delete-reason-${round.id}`} name="reason" maxLength={1000} placeholder="Added twice" />
            </FormField>
            {mutation.isError && (
              <p role="alert" className="text-sm text-destructive">
                The round couldn&apos;t be deleted. Try again.
              </p>
            )}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                Keep round
              </Button>
              <Button type="submit" variant="destructive" disabled={mutation.isPending}>
                {mutation.isPending ? "Deleting…" : "Delete round"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
