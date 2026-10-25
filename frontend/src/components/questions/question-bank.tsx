"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Pill } from "@/components/applications/status-badge";
import { emptyQuestion, QuestionEditor, toQuestionFields, type QuestionDraft } from "@/components/questions/question-editor";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { buttonClass } from "@/lib/button-class";
import { formatDate } from "@/lib/format";
import { createQuestion, getFacets, questionKeys, searchQuestions, type Question } from "@/lib/journals";
import { DIFFICULTY, PRACTICE_STATUS, RESPONSE_QUALITY, ROUND_TYPE } from "@/lib/labels";
import { useCloseOnHide } from "@/lib/use-close-on-hide";

const PAGE_SIZE = 25;
const FILTERS = ["company", "position", "topic", "round_type", "difficulty", "response_quality", "practice_status", "date_from", "date_to"] as const;

export function QuestionBank() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const page = Math.max(1, Number(searchParams.get("page")) || 1);
  const q = searchParams.get("q") ?? "";

  const params: Record<string, string> = { limit: String(PAGE_SIZE), offset: String((page - 1) * PAGE_SIZE) };
  if (q) params.q = q;
  for (const key of FILTERS) {
    const value = searchParams.get(key);
    if (value) params[key] = value;
  }

  const results = useQuery({ queryKey: questionKeys.search(params), queryFn: () => searchQuestions(params), placeholderData: keepPreviousData });
  const facets = useQuery({ queryKey: questionKeys.facets, queryFn: getFacets });

  function setParam(updates: Record<string, string | null>) {
    const next = new URLSearchParams(searchParams);
    for (const [key, value] of Object.entries(updates)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    if (!("page" in updates)) next.delete("page");
    const query = next.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }

  const [searchText, setSearchText] = useState(q);
  const [syncedQ, setSyncedQ] = useState(q);
  if (q !== syncedQ) {
    setSyncedQ(q);
    setSearchText(q);
  }
  useEffect(() => {
    if (searchText.trim() === q) return;
    const timer = setTimeout(() => setParam({ q: searchText.trim() || null }), 300);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only react to typing
  }, [searchText]);

  const total = results.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const filtered = Boolean(q) || FILTERS.some((key) => searchParams.get(key));

  const select = (key: (typeof FILTERS)[number], label: string, options: [string, string][]) => (
    <NativeSelect aria-label={label} value={searchParams.get(key) ?? ""} onChange={(e) => setParam({ [key]: e.target.value || null })} className="w-auto">
      <option value="">{label}</option>
      {options.map(([value, text]) => (
        <option key={value} value={value}>
          {text}
        </option>
      ))}
    </NativeSelect>
  );

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-xl font-semibold tracking-tight">Question bank</h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Every question you&apos;ve recorded, with your original answer. Practise them again and compare.
          </p>
        </div>
        <RecordQuestionButton />
      </div>

      <div className="flex flex-col gap-3" role="search">
        <Input
          type="search"
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          placeholder="Search question text, topic or subject"
          aria-label="Search questions"
          className="w-full sm:w-96"
          maxLength={200}
        />
        <div className="flex flex-wrap items-center gap-2">
          {select("company", "Any company", (facets.data?.companies ?? []).map((c) => [c, c]))}
          {select("topic", "Any topic", (facets.data?.topics ?? []).map((t) => [t, t]))}
          {select("round_type", "Any round", Object.entries(ROUND_TYPE))}
          {select("response_quality", "Any outcome", Object.entries(RESPONSE_QUALITY).map(([k, v]) => [k, v.label]))}
          {select("practice_status", "Any practice status", Object.entries(PRACTICE_STATUS).map(([k, v]) => [k, v.label]))}
          {select("difficulty", "Any difficulty", Object.entries(DIFFICULTY).filter(([k]) => k !== "unknown"))}
          <label className="flex items-center gap-1.5 text-sm text-muted-foreground">
            From
            <Input type="date" value={searchParams.get("date_from") ?? ""} onChange={(e) => setParam({ date_from: e.target.value || null })} className="w-auto" />
          </label>
          <label className="flex items-center gap-1.5 text-sm text-muted-foreground">
            to
            <Input type="date" value={searchParams.get("date_to") ?? ""} onChange={(e) => setParam({ date_to: e.target.value || null })} className="w-auto" />
          </label>
          {filtered && (
            <Link href="/questions" className={buttonClass({ variant: "ghost", size: "sm" }, "text-muted-foreground")}>
              Clear filters
            </Link>
          )}
          <span className="ml-auto text-sm text-muted-foreground tabular-nums" aria-live="polite">
            {results.data ? `${total} question${total === 1 ? "" : "s"}` : ""}
          </span>
        </div>
      </div>

      {results.isPending ? (
        <div aria-hidden className="h-40 animate-pulse rounded-xl bg-muted" />
      ) : results.isError ? (
        <p role="alert" className="text-sm text-destructive">
          Questions couldn&apos;t be loaded. Check that the backend is running, then refresh.
        </p>
      ) : results.data.items.length === 0 ? (
        <p className="surface rounded-xl border border-dashed px-6 py-10 text-center text-sm text-muted-foreground">
          {filtered
            ? "No questions match these filters."
            : "No questions yet. Record them in a journal after an assessment or interview, or add one here."}
        </p>
      ) : (
        <ul className={`divide-y overflow-hidden surface rounded-xl border ${results.isFetching ? "opacity-70" : ""}`}>
          {results.data.items.map((question) => (
            <QuestionRow key={question.id} question={question} />
          ))}
        </ul>
      )}

      {pageCount > 1 && (
        <nav aria-label="Pagination" className="flex items-center justify-between text-sm">
          <button type="button" className={buttonClass({ variant: "outline", size: "sm" })} disabled={page <= 1} onClick={() => setParam({ page: String(page - 1) })}>
            Previous
          </button>
          <span className="text-muted-foreground tabular-nums">
            Page {page} of {pageCount}
          </span>
          <button type="button" className={buttonClass({ variant: "outline", size: "sm" })} disabled={page >= pageCount} onClick={() => setParam({ page: String(page + 1) })}>
            Next
          </button>
        </nav>
      )}
    </div>
  );
}

function QuestionRow({ question }: { question: Question }) {
  const quality = RESPONSE_QUALITY[question.response_quality];
  const practice = PRACTICE_STATUS[question.practice_status];
  const context = [question.company_name, question.round_name].filter(Boolean).join(" · ");
  return (
    <li>
      <Link href={`/questions/${question.id}`} className="flex flex-col gap-2 px-4 py-3.5 hover:bg-muted/50 focus-visible:bg-muted/50 focus-visible:outline-none">
        <span className="text-sm font-medium">{question.text}</span>
        <span className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
          <Pill tone={quality.tone}>{quality.label}</Pill>
          <Pill tone={practice.tone}>{practice.label}</Pill>
          {question.topic && <span>{question.topic}</span>}
          {context && <span>· {context}</span>}
          <span className="tabular-nums">· {formatDate(question.asked_on ?? question.created_at.slice(0, 10))}</span>
          {question.attempt_count > 0 && (
            <span className="tabular-nums">
              · {question.attempt_count} later attempt{question.attempt_count === 1 ? "" : "s"}
            </span>
          )}
        </span>
      </Link>
    </li>
  );
}

function RecordQuestionButton() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<QuestionDraft>(emptyQuestion());
  useCloseOnHide(useCallback(() => setOpen(false), []));
  const mutation = useMutation({
    mutationFn: () => createQuestion(toQuestionFields(draft)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: questionKeys.all });
      setDraft(emptyQuestion());
      setOpen(false);
    },
  });

  return (
    <>
      <Button onClick={() => setOpen(true)}>Record a question</Button>
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
              <DialogTitle>Record a question</DialogTitle>
              <DialogDescription>
                For a question not tied to a journal, such as one from practice. To link it to an interview, add it
                from that interview&apos;s journal instead.
              </DialogDescription>
            </DialogHeader>
            <QuestionEditor idPrefix="new-q" value={draft} onChange={setDraft} />
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
