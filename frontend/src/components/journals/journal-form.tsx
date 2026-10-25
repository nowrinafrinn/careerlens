"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { emptyQuestion, QuestionEditor, toQuestionFields, type QuestionDraft } from "@/components/questions/question-editor";
import { readApiError } from "@/components/form-field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import { applicationKeys, type ApplicationDetail, type RoundType } from "@/lib/applications";
import { buttonClass } from "@/lib/button-class";
import {
  createJournal,
  getTemplates,
  journalKeys,
  questionKeys,
  updateJournal,
  type Journal,
  type JournalTemplate,
} from "@/lib/journals";

function templateForRound(type: RoundType | undefined): JournalTemplate {
  if (type === "online_assessment") return "technical_assessment";
  if (type === "written_exam") return "written_exam";
  if (type?.endsWith("interview")) return "interview";
  return "general";
}

type Props = {
  application: ApplicationDetail;
  journal?: Journal; // present = edit mode (questions are added from the journal page)
  initialRoundId?: string | null;
};

export function JournalForm({ application, journal, initialRoundId }: Props) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const templates = useQuery({ queryKey: journalKeys.templates, queryFn: getTemplates, staleTime: Infinity });

  const initialRound = application.rounds.find((r) => r.id === (journal?.round_id ?? initialRoundId));
  const [roundId, setRoundId] = useState(initialRound?.id ?? "");
  const [template, setTemplate] = useState<JournalTemplate>(journal?.template ?? templateForRound(initialRound?.round_type));
  const [occurredOn, setOccurredOn] = useState(journal?.occurred_on ?? new Date().toLocaleDateString("en-CA"));
  const [responses, setResponses] = useState<Record<string, string>>(journal?.responses ?? {});
  const [feedback, setFeedback] = useState(journal?.interviewer_feedback ?? "");
  const [interpretation, setInterpretation] = useState(journal?.user_interpretation ?? "");
  const [followUp, setFollowUp] = useState(journal?.follow_up_actions ?? "");
  const [questions, setQuestions] = useState<QuestionDraft[]>([]);
  const [error, setError] = useState<string | null>(null);

  const current = templates.data?.find((t) => t.template === template);

  const mutation = useMutation({
    mutationFn: () => {
      // Only answers to this template's prompts are sent (switching template keeps typing in state).
      const keys = new Set(current?.prompts.map((p) => p.key) ?? []);
      const answers = Object.fromEntries(Object.entries(responses).filter(([key, value]) => keys.has(key) && value.trim()));
      const shared = {
        round_id: roundId || null,
        occurred_on: occurredOn || null,
        responses: answers,
        interviewer_feedback: feedback,
        user_interpretation: interpretation,
        follow_up_actions: followUp,
      };
      return journal
        ? updateJournal(journal.id, shared)
        : createJournal({
            ...shared,
            application_id: application.id,
            template,
            questions: questions.filter((q) => q.text.trim()).map(toQuestionFields),
          });
    },
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: applicationKeys.all });
      queryClient.invalidateQueries({ queryKey: questionKeys.all });
      if (!journal) {
        // Next.js keeps this page mounted after navigating away; start fresh next time.
        setResponses({});
        setFeedback("");
        setInterpretation("");
        setFollowUp("");
        setQuestions([]);
      }
      router.push(`/journals/${saved.id}`);
    },
    onError: (err) => setError(readApiError(err).form ?? "Some values are invalid. Check the form and try again."),
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    mutation.mutate();
  }

  if (templates.isPending) return <div aria-hidden className="h-64 animate-pulse rounded-xl bg-muted" />;

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-6">
      <section className="grid gap-4 surface rounded-xl border p-5 sm:grid-cols-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="journal-round">Round</Label>
          <NativeSelect
            id="journal-round"
            value={roundId}
            onChange={(e) => {
              setRoundId(e.target.value);
              if (!journal) setTemplate(templateForRound(application.rounds.find((r) => r.id === e.target.value)?.round_type));
            }}
          >
            <option value="">Not about a specific round</option>
            {application.rounds.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </NativeSelect>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="journal-template">Kind of event</Label>
          <NativeSelect
            id="journal-template"
            value={template}
            disabled={Boolean(journal)}
            onChange={(e) => setTemplate(e.target.value as JournalTemplate)}
          >
            {templates.data?.map((t) => (
              <option key={t.template} value={t.template}>
                {t.label}
              </option>
            ))}
          </NativeSelect>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="journal-date">Date</Label>
          <Input id="journal-date" type="date" value={occurredOn} onChange={(e) => setOccurredOn(e.target.value)} />
        </div>
        {current && <p className="text-sm text-muted-foreground sm:col-span-3">{current.description}</p>}
      </section>

      <section aria-labelledby="prompts-heading" className="flex flex-col gap-4 surface rounded-xl border p-5">
        <div>
          <h2 id="prompts-heading" className="text-sm font-semibold">
            What happened
          </h2>
          <p className="text-sm text-muted-foreground">Answer what&apos;s useful; skip the rest. Write it soon, while you remember.</p>
        </div>
        {current?.prompts.map((prompt) => (
          <div key={prompt.key} className="flex flex-col gap-1.5">
            <Label htmlFor={`prompt-${prompt.key}`}>{prompt.question}</Label>
            {prompt.hint && (
              <p id={`prompt-${prompt.key}-hint`} className="text-xs text-muted-foreground">
                {prompt.hint}
              </p>
            )}
            <Textarea
              id={`prompt-${prompt.key}`}
              value={responses[prompt.key] ?? ""}
              onChange={(e) => setResponses({ ...responses, [prompt.key]: e.target.value })}
              rows={2}
              maxLength={20000}
              aria-describedby={prompt.hint ? `prompt-${prompt.key}-hint` : undefined}
            />
          </div>
        ))}
      </section>

      <section aria-labelledby="feedback-heading" className="flex flex-col gap-4 surface rounded-xl border p-5">
        <div>
          <h2 id="feedback-heading" className="text-sm font-semibold">
            Feedback and your reading of it
          </h2>
          <p className="text-sm text-muted-foreground">
            Kept apart on purpose, so later you can tell what was actually said from what you guessed.
          </p>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="journal-feedback">What the interviewer or recruiter actually told you</Label>
          <Textarea id="journal-feedback" value={feedback} onChange={(e) => setFeedback(e.target.value)} rows={2} maxLength={20000} aria-describedby="journal-feedback-hint" />
          <p id="journal-feedback-hint" className="text-xs text-muted-foreground">
            Only explicit feedback. Leave empty if none was given.
          </p>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="journal-interpretation">Your own interpretation</Label>
          <Textarea id="journal-interpretation" value={interpretation} onChange={(e) => setInterpretation(e.target.value)} rows={2} maxLength={20000} aria-describedby="journal-interpretation-hint" />
          <p id="journal-interpretation-hint" className="text-xs text-muted-foreground">
            How you think it went and why. It&apos;s labelled as yours, so speculation is fine here.
          </p>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="journal-follow-up">Follow-up actions</Label>
          <Textarea id="journal-follow-up" value={followUp} onChange={(e) => setFollowUp(e.target.value)} rows={2} maxLength={20000} />
        </div>
      </section>

      {!journal && (
        <section aria-labelledby="questions-heading" className="flex flex-col gap-4">
          <div>
            <h2 id="questions-heading" className="text-sm font-semibold">
              Questions you were asked
            </h2>
            <p className="text-sm text-muted-foreground">
              Each one goes into your question bank, where you can practise it again and compare with this first answer.
            </p>
          </div>
          {questions.map((question, index) => (
            <fieldset key={index} className="flex flex-col gap-3 surface rounded-xl border p-4">
              <div className="flex items-center justify-between">
                <legend className="text-sm font-medium">Question {index + 1}</legend>
                <Button type="button" variant="ghost" size="sm" className="text-muted-foreground" onClick={() => setQuestions(questions.filter((_, i) => i !== index))}>
                  Remove
                </Button>
              </div>
              <QuestionEditor
                idPrefix={`q${index}`}
                value={question}
                onChange={(next) => setQuestions(questions.map((q, i) => (i === index ? next : q)))}
              />
            </fieldset>
          ))}
          <div>
            <Button type="button" variant="outline" size="sm" onClick={() => setQuestions([...questions, emptyQuestion()])}>
              Add a question
            </Button>
          </div>
        </section>
      )}

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <Link href={journal ? `/journals/${journal.id}` : `/applications/${application.id}`} className={buttonClass({ variant: "outline" })}>
          Cancel
        </Link>
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? "Saving…" : journal ? "Save changes" : "Save journal"}
        </Button>
      </div>
    </form>
  );
}
