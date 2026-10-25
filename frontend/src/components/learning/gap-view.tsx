"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useState, type FormEvent } from "react";

import { Pill } from "@/components/applications/status-badge";
import { FormField } from "@/components/form-field";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import { formatDate, formatDateTime } from "@/lib/format";
import { ATTEMPT_OUTCOME, EVIDENCE_BASIS, GAP_STATUS, GAP_TYPE, LEVEL, TASK_STATUS } from "@/lib/labels";
import {
  addTaskAttempt,
  createTask,
  getGap,
  learningKeys,
  reassessGap,
  updateGap,
  updateTask,
  type AttemptOutcome,
  type GapDetail,
  type GapStatus,
  type GapType,
  type GapUpdate,
  type Level,
  type Task,
  type TaskStatus,
} from "@/lib/learning";
import { useCloseOnHide } from "@/lib/use-close-on-hide";

function useGapMutation<T>(gapId: string, fn: (input: T) => Promise<unknown>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: learningKeys.all });
      queryClient.invalidateQueries({ queryKey: learningKeys.gap(gapId) });
    },
  });
}

export function GapView() {
  const { id } = useParams<{ id: string }>();
  const gap = useQuery({ queryKey: learningKeys.gap(id), queryFn: () => getGap(id) });
  const update = useGapMutation(id, (body: GapUpdate) => updateGap(id, body));

  if (gap.isPending) return <div aria-hidden className="h-64 animate-pulse rounded-xl bg-muted" />;
  if (gap.isError) {
    const notFound = gap.error instanceof ApiError && gap.error.status === 404;
    return <p role="alert" className="text-sm text-destructive">{notFound ? "Skill gap not found." : "This gap couldn't be loaded."}</p>;
  }
  const g = gap.data;

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6">
      <div className="flex flex-col gap-2">
        <Link href="/learning" className="text-sm text-muted-foreground hover:text-foreground">
          ← Learning plan
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex flex-col gap-1">
            <h1 className="text-2xl font-semibold tracking-tight">{g.skill_name}</h1>
            <div className="flex flex-wrap items-center gap-2">
              <Pill tone={GAP_STATUS[g.status].tone}>{GAP_STATUS[g.status].label}</Pill>
              <span className="text-xs text-muted-foreground">Your confidence in this assessment: {LEVEL[g.confidence].toLowerCase()}</span>
            </div>
          </div>
          <ReassessButton gap={g} />
        </div>
      </div>

      <section aria-labelledby="diagnosis-heading" className="flex flex-col gap-4 rounded-xl border bg-background p-5">
        <div>
          <h2 id="diagnosis-heading" className="text-sm font-semibold">
            Your diagnosis
          </h2>
          <p className="text-sm text-muted-foreground">
            CareerLens doesn&apos;t guess what kind of gap this is. Decide from the evidence below.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-4">
          <div className="flex flex-col gap-1.5 sm:col-span-2">
            <Label htmlFor="gap-type">Kind of gap</Label>
            <NativeSelect id="gap-type" value={g.gap_type} onChange={(e) => update.mutate({ gap_type: e.target.value as GapType })} aria-describedby="gap-type-hint">
              {Object.entries(GAP_TYPE).map(([value, meta]) => (
                <option key={value} value={value}>
                  {meta.label}
                </option>
              ))}
            </NativeSelect>
            <p id="gap-type-hint" className="text-xs text-muted-foreground">
              {GAP_TYPE[g.gap_type].description}
            </p>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="gap-priority">Priority</Label>
            <NativeSelect id="gap-priority" value={g.priority} onChange={(e) => update.mutate({ priority: Number(e.target.value) })}>
              {[1, 2, 3, 4, 5].map((p) => (
                <option key={p} value={p}>
                  {p}
                  {p === 1 ? " (highest)" : p === 5 ? " (lowest)" : ""}
                </option>
              ))}
            </NativeSelect>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="gap-importance">Importance</Label>
            <NativeSelect id="gap-importance" value={g.importance} onChange={(e) => update.mutate({ importance: e.target.value as Level })}>
              {Object.entries(LEVEL).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </NativeSelect>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="gap-target">Target date</Label>
            <Input id="gap-target" type="date" value={g.target_date ?? ""} onChange={(e) => update.mutate({ target_date: e.target.value || null })} />
          </div>
          <SaveableText
            id="gap-action"
            label="What you plan to do"
            value={g.recommended_action}
            onSave={(recommended_action) => update.mutate({ recommended_action })}
            className="sm:col-span-3"
          />
        </div>
        {update.isError && <p role="alert" className="text-sm text-destructive">The change couldn&apos;t be saved.</p>}
      </section>

      <section aria-labelledby="evidence-heading" className="flex flex-col gap-3">
        <h2 id="evidence-heading" className="text-base font-semibold">
          Evidence <span className="font-normal text-muted-foreground tabular-nums">({g.evidence.length})</span>
        </h2>
        <ul className="flex flex-col gap-2">
          {g.evidence.map((e) => (
            <li key={e.id} className="rounded-xl border bg-background p-4 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <Pill tone="neutral">{EVIDENCE_BASIS[e.basis]}</Pill>
                <span className="text-xs text-muted-foreground tabular-nums">{formatDateTime(e.created_at)}</span>
              </div>
              {e.requirement_text && (
                <p className="mt-2">
                  Requirement: “{e.requirement_text}”
                  {e.company_name && (
                    <>
                      {" "}
                      ·{" "}
                      <Link href={`/applications/${e.application_id}/analysis`} className="underline underline-offset-4">
                        {e.position_title}, {e.company_name}
                      </Link>
                    </>
                  )}
                </p>
              )}
              {e.question_text && (
                <p className="mt-2">
                  Question:{" "}
                  <Link href={`/questions/${e.question_id}`} className="underline underline-offset-4">
                    {e.question_text}
                  </Link>
                  {e.company_name && <span className="text-muted-foreground"> · {e.company_name}</span>}
                </p>
              )}
              {e.note && <p className="mt-1 text-muted-foreground">{e.note}</p>}
            </li>
          ))}
        </ul>
      </section>

      <TasksSection gap={g} />

      <section aria-labelledby="history-heading" className="flex flex-col gap-3">
        <h2 id="history-heading" className="text-base font-semibold">
          Reassessments
        </h2>
        {g.reassessments.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            None yet. After some practice, reassess the gap and cite the attempt that shows where you are.
          </p>
        ) : (
          <ol className="relative flex flex-col gap-3 border-l pl-4">
            {[...g.reassessments].reverse().map((r) => (
              <li key={r.id} className="text-sm">
                <p className="text-xs text-muted-foreground tabular-nums">{formatDateTime(r.assessed_at)}</p>
                <p>
                  {GAP_STATUS[r.previous_status].label} → <span className="font-medium">{GAP_STATUS[r.new_status].label}</span>{" "}
                  <span className="text-muted-foreground">({LEVEL[r.confidence].toLowerCase()} confidence)</span>
                </p>
                <p>{r.summary}</p>
                {r.cited && <p className="text-muted-foreground">Based on: {r.cited}</p>}
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}

function SaveableText(props: { id: string; label: string; value: string | null; onSave: (v: string | null) => void; className?: string }) {
  const [text, setText] = useState(props.value ?? "");
  const changed = (text.trim() || null) !== (props.value ?? null);
  return (
    <div className={`flex flex-col gap-1.5 ${props.className ?? ""}`}>
      <Label htmlFor={props.id}>{props.label}</Label>
      <div className="flex gap-2">
        <Input id={props.id} value={text} onChange={(e) => setText(e.target.value)} maxLength={2000} />
        <Button type="button" size="sm" variant="outline" disabled={!changed} onClick={() => props.onSave(text.trim() || null)}>
          Save
        </Button>
      </div>
    </div>
  );
}

function TasksSection({ gap }: { gap: GapDetail }) {
  const create = useGapMutation(gap.id, createTask);
  const [title, setTitle] = useState("");
  const [due, setDue] = useState("");

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) return;
    create.mutate(
      { title: title.trim(), skill_gap_id: gap.id, due_date: due || null },
      { onSuccess: () => { setTitle(""); setDue(""); } },
    );
  }

  return (
    <section aria-labelledby="tasks-heading" className="flex flex-col gap-3">
      <h2 id="tasks-heading" className="text-base font-semibold">
        Learning tasks <span className="font-normal text-muted-foreground tabular-nums">({gap.tasks.length})</span>
      </h2>
      {gap.tasks.length > 0 && (
        <ul className="flex flex-col gap-2">
          {gap.tasks.map((task) => (
            <TaskCard key={task.id} task={task} gapId={gap.id} />
          ))}
        </ul>
      )}
      <form onSubmit={onSubmit} className="grid gap-3 rounded-xl border border-dashed bg-background p-4 sm:grid-cols-[minmax(0,1fr)_10rem_auto] sm:items-end">
        <FormField id="new-task" label="New task">
          <Input id="new-task" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} placeholder="Solve 5 timed window-function problems" />
        </FormField>
        <FormField id="new-task-due" label="Due" optional>
          <Input id="new-task-due" type="date" value={due} onChange={(e) => setDue(e.target.value)} />
        </FormField>
        <Button type="submit" disabled={create.isPending || !title.trim()}>
          Add task
        </Button>
      </form>
    </section>
  );
}

function TaskCard({ task, gapId }: { task: Task; gapId: string }) {
  const update = useGapMutation(gapId, (body: { status: TaskStatus }) => updateTask(task.id, body));
  const status = TASK_STATUS[task.status];
  return (
    <li className="flex flex-col gap-3 rounded-xl border bg-background p-4 text-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-medium">{task.title}</p>
          <p className="text-xs text-muted-foreground">
            {task.due_date ? `Due ${formatDate(task.due_date)}` : "No due date"}
            {task.requirement_text && ` · for “${task.requirement_text}”`}
          </p>
        </div>
        <Pill tone={status.tone}>{status.label}</Pill>
      </div>
      {task.attempts.length > 0 && (
        <ul className="flex flex-col gap-1 border-l pl-3 text-muted-foreground">
          {task.attempts.map((a) => (
            <li key={a.id} className="tabular-nums">
              {formatDateTime(a.attempted_at)}: {ATTEMPT_OUTCOME[a.outcome].toLowerCase()}
              {a.duration_minutes !== null && `, ${a.duration_minutes} min`}
              {a.notes && `. ${a.notes}`}
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <Label htmlFor={`status-${task.id}`} className="sr-only">
          Task status
        </Label>
        <NativeSelect id={`status-${task.id}`} value={task.status} onChange={(e) => update.mutate({ status: e.target.value as TaskStatus })} className="w-auto">
          {Object.entries(TASK_STATUS).map(([value, meta]) => (
            <option key={value} value={value}>
              {meta.label}
            </option>
          ))}
        </NativeSelect>
        <LogPracticeButton task={task} gapId={gapId} />
      </div>
    </li>
  );
}

function LogPracticeButton({ task, gapId }: { task: Task; gapId: string }) {
  const [open, setOpen] = useState(false);
  useCloseOnHide(useCallback(() => setOpen(false), []));
  const mutation = useGapMutation(gapId, (body: { outcome: AttemptOutcome; duration_minutes: number | null; notes: string | null }) =>
    addTaskAttempt(task.id, body),
  );

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const minutes = String(data.get("minutes") ?? "");
    mutation.mutate(
      {
        outcome: String(data.get("outcome")) as AttemptOutcome,
        duration_minutes: minutes ? Number(minutes) : null,
        notes: String(data.get("notes") ?? "").trim() || null,
      },
      { onSuccess: () => setOpen(false) },
    );
  }

  return (
    <>
      <Button size="sm" variant="outline" onClick={() => setOpen(true)}>
        Log practice
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <form onSubmit={onSubmit} className="grid gap-4">
            <DialogHeader>
              <DialogTitle>Log practice</DialogTitle>
              <DialogDescription>{task.title}</DialogDescription>
            </DialogHeader>
            <div className="grid grid-cols-2 gap-3">
              <FormField id={`outcome-${task.id}`} label="How it went">
                <NativeSelect id={`outcome-${task.id}`} name="outcome" defaultValue="partial">
                  {Object.entries(ATTEMPT_OUTCOME).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </NativeSelect>
              </FormField>
              <FormField id={`minutes-${task.id}`} label="Minutes" optional>
                <Input id={`minutes-${task.id}`} name="minutes" type="number" min={0} max={1440} inputMode="numeric" />
              </FormField>
            </div>
            <FormField id={`notes-${task.id}`} label="Notes" optional>
              <Textarea id={`notes-${task.id}`} name="notes" rows={2} maxLength={2000} />
            </FormField>
            {mutation.isError && <p role="alert" className="text-sm text-destructive">The practice couldn&apos;t be saved.</p>}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={mutation.isPending}>
                Save
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}

function ReassessButton({ gap }: { gap: GapDetail }) {
  const [open, setOpen] = useState(false);
  useCloseOnHide(useCallback(() => setOpen(false), []));
  const mutation = useGapMutation(gap.id, (body: Parameters<typeof reassessGap>[1]) => reassessGap(gap.id, body));
  const attempts = gap.tasks.flatMap((t) => t.attempts.map((a) => ({ ...a, title: t.title })));

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const cited = String(data.get("cited") ?? "");
    mutation.mutate(
      {
        new_status: String(data.get("status")) as GapStatus,
        confidence: String(data.get("confidence")) as Level,
        summary: String(data.get("summary")).trim(),
        task_attempt_id: cited || null,
      },
      { onSuccess: () => setOpen(false) },
    );
  }

  return (
    <>
      <Button size="sm" onClick={() => setOpen(true)}>
        Reassess
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <form onSubmit={onSubmit} className="grid gap-4">
            <DialogHeader>
              <DialogTitle>Reassess {gap.skill_name}</DialogTitle>
              <DialogDescription>
                Where are you now, and what shows it? This is added to the history; earlier assessments are kept.
              </DialogDescription>
            </DialogHeader>
            <div className="grid grid-cols-2 gap-3">
              <FormField id="reassess-status" label="Status now">
                <NativeSelect id="reassess-status" name="status" defaultValue={gap.status}>
                  {Object.entries(GAP_STATUS).map(([value, meta]) => (
                    <option key={value} value={value}>
                      {meta.label}
                    </option>
                  ))}
                </NativeSelect>
              </FormField>
              <FormField id="reassess-confidence" label="How sure are you?">
                <NativeSelect id="reassess-confidence" name="confidence" defaultValue="medium">
                  {Object.entries(LEVEL).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </NativeSelect>
              </FormField>
            </div>
            <FormField id="reassess-summary" label="What you based it on">
              <Textarea id="reassess-summary" name="summary" required rows={3} maxLength={5000} placeholder="Solved 4 of 5 timed problems without hints." />
            </FormField>
            <FormField id="reassess-cited" label="Practice session that shows it" optional>
              <NativeSelect id="reassess-cited" name="cited" defaultValue="">
                <option value="">None</option>
                {attempts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.title}: {ATTEMPT_OUTCOME[a.outcome].toLowerCase()}, {formatDate(a.attempted_at.slice(0, 10))}
                  </option>
                ))}
              </NativeSelect>
            </FormField>
            {mutation.isError && <p role="alert" className="text-sm text-destructive">The reassessment couldn&apos;t be saved.</p>}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={mutation.isPending}>
                Save reassessment
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
