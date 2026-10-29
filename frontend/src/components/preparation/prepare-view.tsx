"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Pill } from "@/components/applications/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { applicationKeys, getApplication } from "@/lib/applications";
import { buttonClass } from "@/lib/button-class";
import { formatDate, formatDateTime } from "@/lib/format";
import { ROUND_TYPE, SUGGESTION_KIND } from "@/lib/labels";
import { createTask, deleteTask, learningKeys, updateTask, type Task } from "@/lib/learning";
import { getPreparation, listPrepTasks, preparationKeys, type Suggestion, type SuggestionKind } from "@/lib/preparation";

export function PrepareView() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const pathname = usePathname();
  const roundId = useSearchParams().get("round");
  const application = useQuery({ queryKey: applicationKeys.detail(id), queryFn: () => getApplication(id) });
  const prep = useQuery({ queryKey: preparationKeys.suggestions(id, roundId), queryFn: () => getPreparation(id, roundId) });

  const app = application.data;
  const rnd = app?.rounds.find((r) => r.id === roundId);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <Link href={`/applications/${id}`} className="tap self-start text-sm text-muted-foreground hover:text-foreground">
          ← {app ? `${app.position_title}, ${app.company_name}` : "Application"}
        </Link>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex flex-col gap-1">
            <h1 className="text-2xl font-semibold tracking-tight">Prepare{rnd ? ` for ${rnd.name}` : ""}</h1>
            {rnd && (
              <p className="text-sm text-muted-foreground">
                {ROUND_TYPE[rnd.round_type]}
                {rnd.scheduled_at ? ` · ${formatDateTime(rnd.scheduled_at)}` : " · not scheduled"}
              </p>
            )}
          </div>
          {app && (
            <div className="flex items-center gap-2">
              <Label htmlFor="prep-round" className="text-sm text-muted-foreground">
                Preparing for
              </Label>
              <NativeSelect
                id="prep-round"
                value={roundId ?? ""}
                onChange={(e) => router.replace(e.target.value ? `${pathname}?round=${e.target.value}` : pathname, { scroll: false })}
                className="w-auto"
              >
                <option value="">The position in general</option>
                {app.rounds.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </NativeSelect>
            </div>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <section aria-labelledby="suggestions-heading" className="flex min-w-0 flex-col gap-4">
          <div>
            <h2 id="suggestions-heading" className="text-base font-semibold">
              Suggestions
            </h2>
            <p className="text-sm text-muted-foreground">
              {prep.data?.note ?? "Built from this job's requirements, your CV evidence, learning plan and question bank."}{" "}
              Questions here are <strong className="font-medium text-foreground">practice questions</strong>, not
              questions this employer is known to ask.
            </p>
          </div>
          {prep.isPending ? (
            <div aria-hidden className="h-48 animate-pulse rounded-xl bg-muted" />
          ) : prep.isError ? (
            <p role="alert" className="text-sm text-destructive">
              Suggestions couldn&apos;t be loaded.
            </p>
          ) : (
            <SuggestionGroups suggestions={prep.data.suggestions} applicationId={id} roundId={roundId} />
          )}
          {prep.data && (prep.data.analysis_id === null || prep.data.analysis_is_stale) && (
            <Link href={`/applications/${id}/analysis`} className={buttonClass({ variant: "outline", size: "sm" }, "self-start")}>
              {prep.data.analysis_id === null ? "Analyse the job's requirements" : "Re-run the analysis"}
            </Link>
          )}
        </section>

        <Checklist applicationId={id} roundId={roundId} />
      </div>
    </div>
  );
}

function SuggestionGroups({ suggestions, applicationId, roundId }: { suggestions: Suggestion[]; applicationId: string; roundId: string | null }) {
  if (suggestions.length === 0) {
    return (
      <p className="surface rounded-xl border border-dashed p-5 text-sm text-muted-foreground">
        No suggestions yet. Analyse the job&apos;s requirements, or choose a round, to get some. You can always add your
        own checklist items.
      </p>
    );
  }
  const kinds = [...new Set(suggestions.map((s) => s.kind))].sort((a, b) => SUGGESTION_KIND[a].order - SUGGESTION_KIND[b].order);
  return (
    <>
      {kinds.map((kind: SuggestionKind) => (
        <div key={kind} className="flex flex-col gap-2">
          <h3 className="text-sm font-medium text-muted-foreground">{SUGGESTION_KIND[kind].label}</h3>
          <ul className="flex flex-col gap-2">
            {suggestions
              .filter((s) => s.kind === kind)
              .map((s) => (
                <SuggestionCard key={s.title} suggestion={s} applicationId={applicationId} roundId={roundId} />
              ))}
          </ul>
        </div>
      ))}
    </>
  );
}

function SuggestionCard({ suggestion: s, applicationId, roundId }: { suggestion: Suggestion; applicationId: string; roundId: string | null }) {
  const queryClient = useQueryClient();
  const save = useMutation({
    mutationFn: () =>
      createTask({
        kind: "preparation",
        title: s.title.slice(0, 200),
        description: s.detail,
        why: s.why,
        priority: Math.min(5, Math.max(1, s.priority)),
        application_id: applicationId,
        recruitment_round_id: roundId,
        job_requirement_id: s.requirement_id,
        skill_gap_id: s.skill_gap_id,
        question_id: s.question_id,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["applications", "preparation", applicationId] });
      queryClient.invalidateQueries({ queryKey: ["applications", "prep-tasks", applicationId] });
      queryClient.invalidateQueries({ queryKey: learningKeys.all });
    },
  });
  const source = s.skill_gap_id
    ? { href: `/learning/${s.skill_gap_id}`, label: "Open the gap" }
    : s.question_id
      ? { href: `/questions/${s.question_id}`, label: "Open the question" }
      : s.requirement_id
        ? { href: `/applications/${applicationId}/analysis`, label: "See the requirement" }
        : null;

  return (
    <li className="flex flex-col gap-2 surface rounded-xl border p-4 text-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="min-w-0 font-medium">{s.title}</p>
        {s.is_practice_question && <Pill tone="info">Practice question</Pill>}
      </div>
      <p className="text-muted-foreground">{s.detail}</p>
      <p className="text-xs text-muted-foreground">
        <span className="font-medium text-foreground">Why:</span> {s.why}
        {source && (
          <>
            {" "}
            <Link href={source.href} className="underline underline-offset-4">
              {source.label}
            </Link>
          </>
        )}
      </p>
      <div>
        {s.saved_task_id ? (
          <span className="text-xs font-medium text-emerald-700 dark:text-emerald-400">✓ On your checklist</span>
        ) : (
          <Button size="sm" variant="outline" onClick={() => save.mutate()} disabled={save.isPending}>
            Add to checklist
          </Button>
        )}
        {save.isError && <span role="alert" className="ml-2 text-xs text-destructive">It couldn&apos;t be saved.</span>}
      </div>
    </li>
  );
}

function Checklist({ applicationId, roundId }: { applicationId: string; roundId: string | null }) {
  const queryClient = useQueryClient();
  const tasks = useQuery({ queryKey: preparationKeys.checklist(applicationId, roundId), queryFn: () => listPrepTasks(applicationId, roundId) });
  const [title, setTitle] = useState("");
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["applications", "prep-tasks", applicationId] });
    queryClient.invalidateQueries({ queryKey: ["applications", "preparation", applicationId] });
  };
  const add = useMutation({
    mutationFn: () =>
      createTask({ kind: "preparation", title: title.trim(), application_id: applicationId, recruitment_round_id: roundId, why: "Added by you." }),
    onSuccess: () => {
      setTitle("");
      refresh();
    },
  });
  const toggle = useMutation({
    mutationFn: (task: Task) => updateTask(task.id, { status: task.status === "completed" ? "planned" : "completed" }),
    onSuccess: refresh,
  });
  const remove = useMutation({ mutationFn: (task: Task) => deleteTask(task.id), onSuccess: refresh });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (title.trim()) add.mutate();
  }

  const items = tasks.data ?? [];
  const done = items.filter((t) => t.status === "completed").length;

  return (
    <aside aria-labelledby="checklist-heading" className="flex min-w-0 flex-col gap-3 self-start surface rounded-xl border p-4 lg:sticky lg:top-20">
      <div>
        <h2 id="checklist-heading" className="text-base font-semibold">
          Your checklist
        </h2>
        <p className="text-sm text-muted-foreground tabular-nums">
          {items.length === 0 ? "Nothing yet. Add suggestions or your own items." : `${done} of ${items.length} done`}
        </p>
      </div>
      {items.length > 0 && (
        <ul className="flex flex-col gap-2">
          {items.map((task) => (
            <li key={task.id} className="flex items-start gap-2 text-sm">
              <input
                id={`check-${task.id}`}
                type="checkbox"
                checked={task.status === "completed"}
                onChange={() => toggle.mutate(task)}
                className="mt-0.5 size-4 shrink-0 accent-primary"
              />
              <label htmlFor={`check-${task.id}`} className={`min-w-0 flex-1 ${task.status === "completed" ? "text-muted-foreground line-through" : ""}`}>
                {task.title}
                {!roundId && task.round_name && <span className="block text-xs text-muted-foreground no-underline">{task.round_name}</span>}
                {task.due_date && <span className="block text-xs text-muted-foreground">Due {formatDate(task.due_date)}</span>}
              </label>
              <button
                type="button"
                onClick={() => remove.mutate(task)}
                className="tap text-xs text-muted-foreground hover:text-destructive"
                aria-label={`Remove “${task.title}” from the checklist`}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={onSubmit} className="flex flex-col gap-2 border-t pt-3">
        <Label htmlFor="own-item">Add your own item</Label>
        <div className="flex gap-2">
          <Input id="own-item" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} placeholder="Re-read the job posting" />
          <Button type="submit" size="sm" disabled={add.isPending || !title.trim()}>
            Add
          </Button>
        </div>
      </form>
    </aside>
  );
}
