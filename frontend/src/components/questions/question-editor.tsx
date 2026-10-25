"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import type { Difficulty, QuestionFields, ResponseQuality } from "@/lib/journals";
import { CONFIDENCE_LABELS, DIFFICULTY, RESPONSE_QUALITY } from "@/lib/labels";

/** Form state for one question; numbers are kept as strings while typing. */
export type QuestionDraft = {
  text: string;
  topic: string;
  subject: string;
  difficulty: Difficulty;
  original_answer: string;
  response_quality: ResponseQuality;
  confidence: string;
  time_spent_minutes: string;
  difficulty_reason: string;
};

export const emptyQuestion = (): QuestionDraft => ({
  text: "",
  topic: "",
  subject: "",
  difficulty: "unknown",
  original_answer: "",
  response_quality: "partial",
  confidence: "",
  time_spent_minutes: "",
  difficulty_reason: "",
});

const orNull = (value: string) => (value.trim() ? value.trim() : null);

export function toQuestionFields(draft: QuestionDraft): QuestionFields {
  return {
    text: draft.text.trim(),
    topic: orNull(draft.topic),
    subject: orNull(draft.subject),
    difficulty: draft.difficulty,
    original_answer: orNull(draft.original_answer),
    response_quality: draft.response_quality,
    confidence: draft.confidence ? Number(draft.confidence) : null,
    time_spent_minutes: draft.time_spent_minutes ? Number(draft.time_spent_minutes) : null,
    difficulty_reason: orNull(draft.difficulty_reason),
  };
}

type Props = {
  idPrefix: string;
  value: QuestionDraft;
  onChange: (value: QuestionDraft) => void;
};

export function QuestionEditor({ idPrefix, value, onChange }: Props) {
  const set = <K extends keyof QuestionDraft>(key: K, next: QuestionDraft[K]) => onChange({ ...value, [key]: next });
  const id = (name: string) => `${idPrefix}-${name}`;

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <div className="flex flex-col gap-1.5 sm:col-span-2">
        <Label htmlFor={id("text")}>Question</Label>
        <Textarea
          id={id("text")}
          value={value.text}
          onChange={(e) => set("text", e.target.value)}
          rows={2}
          maxLength={5000}
          required
          placeholder="As close to the original wording as you remember"
        />
      </div>
      <div className="flex flex-col gap-1.5 sm:col-span-2">
        <Label htmlFor={id("answer")}>
          Your answer at the time <span className="font-normal text-muted-foreground">(optional)</span>
        </Label>
        <Textarea
          id={id("answer")}
          value={value.original_answer}
          onChange={(e) => set("original_answer", e.target.value)}
          rows={2}
          maxLength={20000}
          aria-describedby={id("answer-hint")}
        />
        <p id={id("answer-hint")} className="text-xs text-muted-foreground">
          What you actually said, or an outline. Kept as it is: later tries are saved separately.
        </p>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={id("quality")}>How it went</Label>
        <NativeSelect id={id("quality")} value={value.response_quality} onChange={(e) => set("response_quality", e.target.value as ResponseQuality)}>
          {Object.entries(RESPONSE_QUALITY).map(([key, meta]) => (
            <option key={key} value={key}>
              {meta.label}
            </option>
          ))}
        </NativeSelect>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={id("confidence")}>
          Confidence <span className="font-normal text-muted-foreground">(optional)</span>
        </Label>
        <NativeSelect id={id("confidence")} value={value.confidence} onChange={(e) => set("confidence", e.target.value)}>
          <option value="">Not recorded</option>
          {Object.entries(CONFIDENCE_LABELS).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </NativeSelect>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={id("topic")}>
          Topic <span className="font-normal text-muted-foreground">(optional)</span>
        </Label>
        <Input id={id("topic")} value={value.topic} onChange={(e) => set("topic", e.target.value)} maxLength={100} placeholder="SQL joins, system design…" />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={id("difficulty")}>Difficulty</Label>
        <NativeSelect id={id("difficulty")} value={value.difficulty} onChange={(e) => set("difficulty", e.target.value as Difficulty)}>
          {Object.entries(DIFFICULTY).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </NativeSelect>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={id("time")}>
          Minutes spent <span className="font-normal text-muted-foreground">(optional)</span>
        </Label>
        <Input id={id("time")} type="number" min={0} max={1440} inputMode="numeric" value={value.time_spent_minutes} onChange={(e) => set("time_spent_minutes", e.target.value)} />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={id("subject")}>
          Subject <span className="font-normal text-muted-foreground">(optional)</span>
        </Label>
        <Input id={id("subject")} value={value.subject} onChange={(e) => set("subject", e.target.value)} maxLength={100} placeholder="Databases, behavioural…" />
      </div>
      <div className="flex flex-col gap-1.5 sm:col-span-2">
        <Label htmlFor={id("reason")}>
          What made it hard <span className="font-normal text-muted-foreground">(optional)</span>
        </Label>
        <Input
          id={id("reason")}
          value={value.difficulty_reason}
          onChange={(e) => set("difficulty_reason", e.target.value)}
          maxLength={2000}
          placeholder="Didn't know the concept, couldn't apply it, ran out of time, couldn't explain it…"
        />
      </div>
    </div>
  );
}
