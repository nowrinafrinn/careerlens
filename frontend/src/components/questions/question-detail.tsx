"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";

import { Pill } from "@/components/applications/status-badge";
import { AddToPlan } from "@/components/learning/add-to-plan";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import { formatDate, formatDateTime } from "@/lib/format";
import {
  addAttempt,
  getQuestion,
  questionKeys,
  updateQuestion,
  type Difficulty,
  type PracticeStatus,
  type QuestionDetail as Detail,
  type QuestionUpdate,
  type ResponseQuality,
} from "@/lib/journals";
import { CONFIDENCE_LABELS, DIFFICULTY, PRACTICE_STATUS, RESPONSE_QUALITY } from "@/lib/labels";
import { gapFromQuestion } from "@/lib/learning";

export function QuestionDetail() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const question = useQuery({ queryKey: questionKeys.detail(id), queryFn: () => getQuestion(id) });
  const update = useMutation({
    mutationFn: (body: QuestionUpdate) => updateQuestion(id, body),
    onSuccess: (saved) => {
      queryClient.setQueryData(questionKeys.detail(id), saved);
      queryClient.invalidateQueries({ queryKey: ["questions", "search"] });
      queryClient.invalidateQueries({ queryKey: questionKeys.facets });
    },
  });

  if (question.isPending) return <div aria-hidden className="h-64 animate-pulse rounded-xl bg-muted" />;
  if (question.isError) {
    const notFound = question.error instanceof ApiError && question.error.status === 404;
    return <p role="alert" className="text-sm text-destructive">{notFound ? "Question not found." : "This question couldn't be loaded."}</p>;
  }

  const q = question.data;
  const latest = q.latest_attempt;

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6">
      <div className="flex flex-col gap-2">
        <Link href="/questions" className="text-sm text-muted-foreground hover:text-foreground">
          ← Question bank
        </Link>
        <h1 className="text-xl font-semibold tracking-tight text-balance">{q.text}</h1>
        <p className="text-sm text-muted-foreground">
          {q.company_name ? (
            <Link href={`/applications/${q.application_id}`} className="underline underline-offset-4">
              {q.position_title}, {q.company_name}
            </Link>
          ) : (
            "Not linked to an application"
          )}
          {q.round_name && ` · ${q.round_name}`}
          {q.journal_id && (
            <>
              {" · "}
              <Link href={`/journals/${q.journal_id}`} className="underline underline-offset-4">
                journal
              </Link>
            </>
          )}
          {` · ${formatDate(q.asked_on ?? q.created_at.slice(0, 10))}`}
        </p>
      </div>

      <section aria-label="Details" className="grid gap-3 rounded-xl border bg-background p-4 sm:grid-cols-4">
        <Meta label="Practice status" id="meta-practice">
          <NativeSelect id="meta-practice" value={q.practice_status} onChange={(e) => update.mutate({ practice_status: e.target.value as PracticeStatus })}>
            {Object.entries(PRACTICE_STATUS).map(([key, meta]) => (
              <option key={key} value={key}>
                {meta.label}
              </option>
            ))}
          </NativeSelect>
        </Meta>
        <Meta label="Difficulty" id="meta-difficulty">
          <NativeSelect id="meta-difficulty" value={q.difficulty} onChange={(e) => update.mutate({ difficulty: e.target.value as Difficulty })}>
            {Object.entries(DIFFICULTY).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </NativeSelect>
        </Meta>
        <Meta label="Topic" id="meta-topic">
          <SaveOnBlur id="meta-topic" value={q.topic} onSave={(topic) => update.mutate({ topic })} />
        </Meta>
        <Meta label="Subject" id="meta-subject">
          <SaveOnBlur id="meta-subject" value={q.subject} onSave={(subject) => update.mutate({ subject })} />
        </Meta>
        {update.isError && <p role="alert" className="text-sm text-destructive sm:col-span-4">The change couldn&apos;t be saved.</p>}
      </section>

      <section aria-labelledby="compare-heading" className="flex flex-col gap-3">
        <h2 id="compare-heading" className="text-base font-semibold">
          Then and now
        </h2>
        <div className="grid gap-3 md:grid-cols-2">
          <AnswerCard
            title="Your answer at the time"
            note="Recorded with the question; never changed."
            answer={q.original_answer}
            quality={q.response_quality}
            confidence={q.confidence}
            minutes={q.time_spent_minutes}
            extra={q.difficulty_reason ? `What made it hard: ${q.difficulty_reason}` : null}
          />
          {latest ? (
            <AnswerCard
              title="Your latest attempt"
              note={formatDateTime(latest.attempted_at)}
              answer={latest.answer}
              quality={latest.response_quality}
              confidence={latest.confidence}
              minutes={latest.time_spent_minutes}
              extra={latest.notes}
            />
          ) : (
            <div className="flex items-center rounded-xl border border-dashed bg-background p-4 text-sm text-muted-foreground">
              No later attempts yet. Try it again below without looking at the solution, then compare.
            </div>
          )}
        </div>
      </section>

      {(q.skill_gap_id || [q.response_quality, ...q.attempts.map((a) => a.response_quality)].some((r) => r === "partial" || r === "could_not_answer")) && (
        <section aria-label="Learning plan" className="flex flex-col gap-2 rounded-xl border bg-background p-4 text-sm">
          <p>
            {q.skill_gap_id
              ? "This question is evidence for a gap in your learning plan."
              : "You struggled with this question. Add its topic to your learning plan to practise it deliberately."}
          </p>
          <AddToPlan
            existingGapId={q.skill_gap_id}
            skillOptions={q.topic ? [q.topic] : []}
            add={(skill) => gapFromQuestion(q.id, skill ?? q.topic ?? undefined)}
            refresh={[[...questionKeys.detail(q.id)]]}
          />
          {!q.topic && !q.skill_gap_id && (
            <p className="text-xs text-muted-foreground">Set a topic above first; it becomes the skill&apos;s name.</p>
          )}
        </section>
      )}

      <AttemptForm question={q} />

      <VerifiedSolution question={q} onSave={(verified_solution) => update.mutate({ verified_solution })} saving={update.isPending} />

      {q.ai_suggestion && (
        <section className="rounded-xl border border-dashed bg-background p-4 text-sm">
          <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">AI-generated suggestion · not verified</p>
          <p className="mt-1 whitespace-pre-wrap">{q.ai_suggestion}</p>
        </section>
      )}

      {q.attempts.length > 0 && (
        <section aria-labelledby="attempts-heading" className="flex flex-col gap-3">
          <h2 id="attempts-heading" className="text-base font-semibold">
            All attempts <span className="font-normal text-muted-foreground tabular-nums">({q.attempts.length})</span>
          </h2>
          <ol className="flex flex-col gap-2">
            {[...q.attempts].reverse().map((attempt) => (
              <li key={attempt.id} className="rounded-xl border bg-background p-4 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-muted-foreground tabular-nums">{formatDateTime(attempt.attempted_at)}</span>
                  <Pill tone={RESPONSE_QUALITY[attempt.response_quality].tone}>{RESPONSE_QUALITY[attempt.response_quality].label}</Pill>
                  {attempt.confidence && <span className="text-xs text-muted-foreground">Confidence {attempt.confidence}/5</span>}
                  {attempt.time_spent_minutes !== null && <span className="text-xs text-muted-foreground tabular-nums">{attempt.time_spent_minutes} min</span>}
                </div>
                {attempt.answer && <p className="mt-2 whitespace-pre-wrap">{attempt.answer}</p>}
                {attempt.notes && <p className="mt-1 text-muted-foreground">{attempt.notes}</p>}
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}

function Meta({ label, id, children }: { label: string; id: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id} className="text-xs text-muted-foreground">
        {label}
      </Label>
      {children}
    </div>
  );
}

function SaveOnBlur({ id, value, onSave }: { id: string; value: string | null; onSave: (value: string | null) => void }) {
  const [text, setText] = useState(value ?? "");
  return (
    <Input
      id={id}
      value={text}
      maxLength={100}
      onChange={(e) => setText(e.target.value)}
      onBlur={() => {
        if ((text.trim() || null) !== (value ?? null)) onSave(text.trim() || null);
      }}
    />
  );
}

function AnswerCard(props: {
  title: string;
  note: string;
  answer: string | null;
  quality: ResponseQuality;
  confidence: number | null;
  minutes: number | null;
  extra: string | null;
}) {
  const quality = RESPONSE_QUALITY[props.quality];
  return (
    <div className="flex flex-col gap-2 rounded-xl border bg-background p-4 text-sm">
      <div>
        <p className="font-medium">{props.title}</p>
        <p className="text-xs text-muted-foreground">{props.note}</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Pill tone={quality.tone}>{quality.label}</Pill>
        <span className="text-xs text-muted-foreground tabular-nums">
          {props.confidence ? `Confidence ${props.confidence}/5` : "Confidence not recorded"}
          {props.minutes !== null ? ` · ${props.minutes} min` : ""}
        </span>
      </div>
      <p className="whitespace-pre-wrap">{props.answer ?? <span className="text-muted-foreground">No answer written down.</span>}</p>
      {props.extra && <p className="text-muted-foreground">{props.extra}</p>}
    </div>
  );
}

function AttemptForm({ question }: { question: Detail }) {
  const queryClient = useQueryClient();
  const [answer, setAnswer] = useState("");
  const [quality, setQuality] = useState<ResponseQuality>("partial");
  const [confidence, setConfidence] = useState("");
  const [minutes, setMinutes] = useState("");
  const [notes, setNotes] = useState("");
  const mutation = useMutation({
    mutationFn: () =>
      addAttempt(question.id, {
        answer: answer.trim() || null,
        response_quality: quality,
        confidence: confidence ? Number(confidence) : null,
        time_spent_minutes: minutes ? Number(minutes) : null,
        notes: notes.trim() || null,
      }),
    onSuccess: (saved) => {
      queryClient.setQueryData(questionKeys.detail(question.id), saved);
      queryClient.invalidateQueries({ queryKey: ["questions", "search"] });
      setAnswer("");
      setConfidence("");
      setMinutes("");
      setNotes("");
    },
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <section aria-labelledby="try-heading" className="rounded-xl border bg-background p-4">
      <h2 id="try-heading" className="text-base font-semibold">
        Try it again
      </h2>
      <p className="text-sm text-muted-foreground">Answer from memory first, then record how it went honestly.</p>
      <form onSubmit={onSubmit} className="mt-3 grid gap-3 sm:grid-cols-3">
        <div className="flex flex-col gap-1.5 sm:col-span-3">
          <Label htmlFor="attempt-answer">Your answer</Label>
          <Textarea id="attempt-answer" value={answer} onChange={(e) => setAnswer(e.target.value)} rows={3} maxLength={20000} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="attempt-quality">How it went</Label>
          <NativeSelect id="attempt-quality" value={quality} onChange={(e) => setQuality(e.target.value as ResponseQuality)}>
            {Object.entries(RESPONSE_QUALITY).map(([key, meta]) => (
              <option key={key} value={key}>
                {meta.label}
              </option>
            ))}
          </NativeSelect>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="attempt-confidence">Confidence</Label>
          <NativeSelect id="attempt-confidence" value={confidence} onChange={(e) => setConfidence(e.target.value)}>
            <option value="">Not recorded</option>
            {Object.entries(CONFIDENCE_LABELS).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </NativeSelect>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="attempt-minutes">Minutes</Label>
          <Input id="attempt-minutes" type="number" min={0} max={1440} inputMode="numeric" value={minutes} onChange={(e) => setMinutes(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1.5 sm:col-span-3">
          <Label htmlFor="attempt-notes">
            Notes <span className="font-normal text-muted-foreground">(optional)</span>
          </Label>
          <Input id="attempt-notes" value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={2000} placeholder="What still felt shaky?" />
        </div>
        {mutation.isError && <p role="alert" className="text-sm text-destructive sm:col-span-3">The attempt couldn&apos;t be saved.</p>}
        <div className="sm:col-span-3">
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? "Saving…" : "Save attempt"}
          </Button>
        </div>
      </form>
    </section>
  );
}

function VerifiedSolution({ question, onSave, saving }: { question: Detail; onSave: (text: string | null) => void; saving: boolean }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(question.verified_solution ?? "");
  return (
    <section aria-labelledby="solution-heading" className="rounded-xl border bg-background p-4 text-sm">
      <div className="flex items-center justify-between gap-2">
        <h2 id="solution-heading" className="text-base font-semibold">
          Verified solution
        </h2>
        {!editing && (
          <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
            {question.verified_solution ? "Edit" : "Add"}
          </Button>
        )}
      </div>
      <p className="text-muted-foreground">An answer you&apos;ve checked against a reliable source. Kept separate from your own attempts.</p>
      {editing ? (
        <div className="mt-3 flex flex-col gap-2">
          <Label htmlFor="verified-solution" className="sr-only">
            Verified solution
          </Label>
          <Textarea id="verified-solution" value={text} onChange={(e) => setText(e.target.value)} rows={5} maxLength={20000} />
          <div className="flex gap-2">
            <Button
              size="sm"
              disabled={saving}
              onClick={() => {
                onSave(text.trim() || null);
                setEditing(false);
              }}
            >
              Save solution
            </Button>
            <Button size="sm" variant="outline" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : question.verified_solution ? (
        <p className="mt-2 whitespace-pre-wrap">{question.verified_solution}</p>
      ) : null}
    </section>
  );
}
