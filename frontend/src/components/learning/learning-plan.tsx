"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useState, type FormEvent } from "react";

import { Pill } from "@/components/applications/status-badge";
import { FormField } from "@/components/form-field";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { EVIDENCE_BASIS, GAP_STATUS, GAP_TYPE, LEVEL } from "@/lib/labels";
import { createGap, learningKeys, listGaps, type GapSummary, type GapType } from "@/lib/learning";
import { useCloseOnHide } from "@/lib/use-close-on-hide";

export function LearningPlan() {
  const gaps = useQuery({ queryKey: learningKeys.gaps, queryFn: listGaps });

  const active = gaps.data?.filter((g) => g.status === "open" || g.status === "improving") ?? [];
  const closed = gaps.data?.filter((g) => g.status === "resolved" || g.status === "dismissed") ?? [];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex max-w-2xl flex-col gap-1">
          <h1 className="text-xl font-semibold tracking-tight">Learning plan</h1>
          <p className="text-sm text-muted-foreground">
            Skills to work on, each backed by evidence: a requirement you said you don&apos;t have yet, a question you
            struggled with, or your own note. Ordered by what to do next: open gaps first, then your priority, how
            important the skill is, and how much evidence supports it.
          </p>
        </div>
        <AddGapButton />
      </div>

      {gaps.isPending ? (
        <div aria-hidden className="h-40 animate-pulse rounded-xl bg-muted" />
      ) : gaps.isError ? (
        <p role="alert" className="text-sm text-destructive">
          The learning plan couldn&apos;t be loaded. Check that the backend is running, then refresh.
        </p>
      ) : gaps.data.length === 0 ? (
        <div className="flex flex-col gap-2 surface rounded-xl border border-dashed p-6 text-sm text-muted-foreground">
          <p className="font-medium text-foreground">Nothing in your plan yet</p>
          <p>Gaps come from real evidence. Add one from:</p>
          <ul className="list-disc pl-5">
            <li>a requirement in an analysis, after you mark it &quot;I don&apos;t have this yet&quot; or &quot;I&apos;m learning this&quot;;</li>
            <li>a question you partly answered or couldn&apos;t answer, from its page in the question bank;</li>
            <li>or directly, with &quot;Add a skill gap&quot;.</li>
          </ul>
        </div>
      ) : (
        <>
          <GapList title="To work on" gaps={active} empty="No open gaps." />
          {closed.length > 0 && <GapList title="Resolved or dismissed" gaps={closed} empty="" />}
        </>
      )}
    </div>
  );
}

function GapList({ title, gaps, empty }: { title: string; gaps: GapSummary[]; empty: string }) {
  return (
    <section aria-label={title} className="flex flex-col gap-3">
      <h2 className="text-base font-semibold">
        {title} <span className="font-normal text-muted-foreground tabular-nums">({gaps.length})</span>
      </h2>
      {gaps.length === 0 ? (
        <p className="text-sm text-muted-foreground">{empty}</p>
      ) : (
        <ol className="flex flex-col gap-2">
          {gaps.map((gap) => (
            <GapCard key={gap.id} gap={gap} />
          ))}
        </ol>
      )}
    </section>
  );
}

function evidenceLine(gap: GapSummary): string {
  const parts = Object.entries(gap.evidence_by_basis).map(([basis, n]) => `${n} × ${EVIDENCE_BASIS[basis as keyof typeof EVIDENCE_BASIS].toLowerCase()}`);
  const jobs = gap.application_count > 0 ? `${gap.application_count} application${gap.application_count === 1 ? "" : "s"} · ` : "";
  return jobs + parts.join(" · ");
}

function GapCard({ gap }: { gap: GapSummary }) {
  const status = GAP_STATUS[gap.status];
  return (
    <li>
      <Link
        href={`/learning/${gap.id}`}
        className="flex flex-col gap-2 surface rounded-xl border p-4 transition-colors hover:bg-muted/50 focus-visible:bg-muted/50 focus-visible:outline-none"
      >
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="font-medium">{gap.skill_name}</p>
            <p className="text-xs text-muted-foreground">
              Priority {gap.priority} · {LEVEL[gap.importance]} importance · {GAP_TYPE[gap.gap_type].label}
              {gap.target_date && ` · target ${formatDate(gap.target_date)}`}
            </p>
          </div>
          <Pill tone={status.tone}>{status.label}</Pill>
        </div>
        <p className="text-sm text-muted-foreground">Evidence: {evidenceLine(gap)}</p>
        <p className="text-sm text-muted-foreground tabular-nums">
          {gap.task_count === 0 ? "No tasks yet" : `${gap.completed_task_count} of ${gap.task_count} tasks completed`}
        </p>
      </Link>
    </li>
  );
}

function AddGapButton() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<{ message: string; existingId?: string } | null>(null);
  useCloseOnHide(useCallback(() => setOpen(false), []));
  const mutation = useMutation({
    mutationFn: createGap,
    onSuccess: (gap) => {
      queryClient.invalidateQueries({ queryKey: learningKeys.all });
      setOpen(false);
      router.push(`/learning/${gap.id}`);
    },
    onError: (err) => {
      if (err instanceof ApiError && err.code === "gap_exists") {
        setError({ message: err.message, existingId: (err.details as { skill_gap_id?: string })?.skill_gap_id });
      } else {
        setError({ message: err instanceof ApiError ? err.message : "The gap couldn't be saved." });
      }
    },
  });

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setError(null);
    mutation.mutate({
      skill_name: String(data.get("skill_name")).trim(),
      reason: String(data.get("reason")).trim(),
      gap_type: String(data.get("gap_type")) as GapType,
      priority: Number(data.get("priority")),
    });
  }

  return (
    <>
      <Button onClick={() => setOpen(true)}>Add a skill gap</Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <form onSubmit={onSubmit} className="grid gap-4">
            <DialogHeader>
              <DialogTitle>Add a skill gap</DialogTitle>
              <DialogDescription>Something you want to learn or improve, in your own words.</DialogDescription>
            </DialogHeader>
            <FormField id="gap-skill" label="Skill">
              <Input id="gap-skill" name="skill_name" required maxLength={100} placeholder="SQL window functions" />
            </FormField>
            <FormField id="gap-reason" label="Why you think it's a gap" hint="Saved as evidence you provided.">
              <Textarea id="gap-reason" name="reason" required maxLength={2000} rows={2} aria-describedby="gap-reason-hint" />
            </FormField>
            <div className="grid grid-cols-2 gap-3">
              <FormField id="gap-type" label="Kind of gap">
                <NativeSelect id="gap-type" name="gap_type" defaultValue="unclassified">
                  {Object.entries(GAP_TYPE).map(([value, meta]) => (
                    <option key={value} value={value}>
                      {meta.label}
                    </option>
                  ))}
                </NativeSelect>
              </FormField>
              <FormField id="gap-priority" label="Priority">
                <NativeSelect id="gap-priority" name="priority" defaultValue="3">
                  {[1, 2, 3, 4, 5].map((p) => (
                    <option key={p} value={p}>
                      {p}
                      {p === 1 ? " (highest)" : p === 5 ? " (lowest)" : ""}
                    </option>
                  ))}
                </NativeSelect>
              </FormField>
            </div>
            {error && (
              <p role="alert" className="text-sm text-destructive">
                {error.message}{" "}
                {error.existingId && (
                  <Link href={`/learning/${error.existingId}`} className="text-foreground underline underline-offset-4">
                    Open it
                  </Link>
                )}
              </p>
            )}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={mutation.isPending}>
                Add to plan
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
