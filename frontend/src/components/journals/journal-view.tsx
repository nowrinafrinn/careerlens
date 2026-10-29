"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useState } from "react";

import { Pill } from "@/components/applications/status-badge";
import { emptyQuestion, QuestionEditor, toQuestionFields, type QuestionDraft } from "@/components/questions/question-editor";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { LoadError } from "@/components/load-error";
import { applicationKeys } from "@/lib/applications";
import { buttonClass } from "@/lib/button-class";
import { formatDate } from "@/lib/format";
import {
  addJournalQuestions,
  deleteJournal,
  getJournal,
  getTemplates,
  journalKeys,
  questionKeys,
  type Journal,
} from "@/lib/journals";
import { PRACTICE_STATUS, RESPONSE_QUALITY } from "@/lib/labels";
import { useCloseOnHide } from "@/lib/use-close-on-hide";

export function JournalView() {
  const { id } = useParams<{ id: string }>();
  const journal = useQuery({ queryKey: journalKeys.detail(id), queryFn: () => getJournal(id) });
  const templates = useQuery({ queryKey: journalKeys.templates, queryFn: getTemplates, staleTime: Infinity });

  if (journal.isPending || templates.isPending) return <div aria-hidden className="h-64 animate-pulse rounded-xl bg-muted" />;
  if (journal.isError || templates.isError) {
    return <LoadError error={journal.error ?? templates.error} thing="Journal" backHref="/applications" backLabel="Back to applications" />;
  }

  const j = journal.data;
  const template = templates.data.find((t) => t.template === j.template);
  const answered = template?.prompts.filter((p) => j.responses[p.key]) ?? [];

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <div className="flex flex-col gap-2">
        <Link href={`/applications/${j.application_id}`} className="tap self-start text-sm text-muted-foreground hover:text-foreground">
          ← {j.position_title}, {j.company_name}
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm text-muted-foreground">
              {template?.label ?? "Journal"}
              {j.round_name ? ` · ${j.round_name}` : ""}
              {j.occurred_on ? ` · ${formatDate(j.occurred_on)}` : ""}
            </p>
            <h1 className="text-2xl font-semibold tracking-tight">Journal</h1>
          </div>
          <div className="flex gap-2">
            <Link href={`/journals/${j.id}/edit`} className={buttonClass({ variant: "outline", size: "sm" })}>
              Edit
            </Link>
            <DeleteJournalButton journal={j} />
          </div>
        </div>
      </div>

      <section aria-labelledby="answers-heading" className="flex flex-col gap-4 surface rounded-xl border p-5">
        <h2 id="answers-heading" className="sr-only">
          Answers
        </h2>
        {answered.length === 0 ? (
          <p className="text-sm text-muted-foreground">No prompts answered.</p>
        ) : (
          answered.map((prompt) => (
            <div key={prompt.key}>
              <h3 className="text-sm font-medium">{prompt.question}</h3>
              <p className="mt-1 text-sm whitespace-pre-wrap">{j.responses[prompt.key]}</p>
            </div>
          ))
        )}
      </section>

      {(j.interviewer_feedback || j.user_interpretation || j.follow_up_actions) && (
        <section aria-labelledby="feedback-heading" className="grid gap-4 sm:grid-cols-2">
          <h2 id="feedback-heading" className="sr-only">
            Feedback
          </h2>
          <div className="surface rounded-xl border p-4">
            <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">What you were told</p>
            <p className="mt-1 text-sm whitespace-pre-wrap">{j.interviewer_feedback ?? "No explicit feedback recorded."}</p>
          </div>
          <div className="surface rounded-xl border border-dashed p-4">
            <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Your interpretation</p>
            <p className="mt-1 text-sm whitespace-pre-wrap">{j.user_interpretation ?? "None recorded."}</p>
          </div>
          {j.follow_up_actions && (
            <div className="surface rounded-xl border p-4 sm:col-span-2">
              <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Follow-up actions</p>
              <p className="mt-1 text-sm whitespace-pre-wrap">{j.follow_up_actions}</p>
            </div>
          )}
        </section>
      )}

      <section aria-labelledby="journal-questions" className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-3">
          <h2 id="journal-questions" className="text-base font-semibold">
            Questions <span className="font-normal text-muted-foreground tabular-nums">({j.questions.length})</span>
          </h2>
          <AddQuestionsButton journal={j} />
        </div>
        {j.questions.length === 0 ? (
          <p className="surface rounded-xl border border-dashed p-5 text-sm text-muted-foreground">
            No questions recorded. Add the ones you remember so you can practise them later.
          </p>
        ) : (
          <ul className="divide-y overflow-hidden surface rounded-xl border">
            {j.questions.map((q) => (
              <li key={q.id}>
                <Link href={`/questions/${q.id}`} className="flex flex-col gap-1.5 px-4 py-3 hover:bg-muted/50">
                  <span className="text-sm">{q.text}</span>
                  <span className="flex flex-wrap gap-1.5">
                    <Pill tone={RESPONSE_QUALITY[q.response_quality].tone}>{RESPONSE_QUALITY[q.response_quality].label}</Pill>
                    <Pill tone={PRACTICE_STATUS[q.practice_status].tone}>{PRACTICE_STATUS[q.practice_status].label}</Pill>
                    {q.topic && <span className="text-xs text-muted-foreground">{q.topic}</span>}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function AddQuestionsButton({ journal }: { journal: Journal }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<QuestionDraft>(emptyQuestion());
  useCloseOnHide(useCallback(() => setOpen(false), []));
  const mutation = useMutation({
    mutationFn: () => addJournalQuestions(journal.id, [toQuestionFields(draft)]),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: journalKeys.detail(journal.id) });
      queryClient.invalidateQueries({ queryKey: questionKeys.all });
      setDraft(emptyQuestion());
      setOpen(false);
    },
  });

  return (
    <>
      <Button size="sm" variant="outline" onClick={() => setOpen(true)}>
        Add a question
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-xl">
          <form
            className="grid gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (draft.text.trim()) mutation.mutate();
            }}
          >
            <DialogHeader>
              <DialogTitle>Add a question</DialogTitle>
              <DialogDescription>It&apos;s linked to this journal and goes into your question bank.</DialogDescription>
            </DialogHeader>
            <QuestionEditor idPrefix="add-q" value={draft} onChange={setDraft} />
            {mutation.isError && <p role="alert" className="text-sm text-destructive">The question couldn&apos;t be saved.</p>}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={mutation.isPending || !draft.text.trim()}>
                Save question
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}

function DeleteJournalButton({ journal }: { journal: Journal }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  useCloseOnHide(useCallback(() => setOpen(false), []));
  const mutation = useMutation({
    mutationFn: () => deleteJournal(journal.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: applicationKeys.all });
      queryClient.invalidateQueries({ queryKey: questionKeys.all });
      router.push(`/applications/${journal.application_id}`);
    },
  });
  return (
    <>
      <Button size="sm" variant="ghost" className="text-muted-foreground" onClick={() => setOpen(true)}>
        Delete
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Delete this journal?</DialogTitle>
            <DialogDescription>
              The journal text is deleted permanently. Its {journal.questions.length} question
              {journal.questions.length === 1 ? "" : "s"} stay in your question bank.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Keep it
            </Button>
            <Button variant="destructive" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
              Delete journal
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
