"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { buttonClass } from "@/lib/button-class";
import { formatDate } from "@/lib/format";
import { getTemplates, journalKeys, listJournals } from "@/lib/journals";

export function JournalsSection({ applicationId }: { applicationId: string }) {
  const journals = useQuery({ queryKey: journalKeys.forApplication(applicationId), queryFn: () => listJournals(applicationId) });
  const templates = useQuery({ queryKey: journalKeys.templates, queryFn: getTemplates, staleTime: Infinity });
  const label = (template: string) => templates.data?.find((t) => t.template === template)?.label ?? "Journal";

  return (
    <section aria-labelledby="journals-heading" className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-4">
        <h2 id="journals-heading" className="text-base font-semibold">
          Journals
        </h2>
        <Link href={`/applications/${applicationId}/journals/new`} className={buttonClass({ size: "sm", variant: "outline" })}>
          Write a journal
        </Link>
      </div>
      {journals.isPending ? (
        <div aria-hidden className="h-16 animate-pulse rounded-xl bg-muted" />
      ) : journals.isError ? (
        <p className="text-sm text-destructive">Journals couldn&apos;t be loaded.</p>
      ) : journals.data.length === 0 ? (
        <p className="surface rounded-xl border border-dashed px-5 py-6 text-sm text-muted-foreground">
          After an assessment or interview, write down what happened and the questions you were asked. They become
          the evidence for what to practise next.
        </p>
      ) : (
        <ul className="divide-y overflow-hidden surface rounded-xl border">
          {journals.data.map((journal) => (
            <li key={journal.id}>
              <Link href={`/journals/${journal.id}`} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm hover:bg-muted/50">
                <span>
                  <span className="font-medium">{label(journal.template)}</span>
                  {journal.round_name && <span className="text-muted-foreground"> · {journal.round_name}</span>}
                </span>
                <span className="text-muted-foreground tabular-nums">
                  {journal.questions.length} question{journal.questions.length === 1 ? "" : "s"}
                  {journal.occurred_on && ` · ${formatDate(journal.occurred_on)}`}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
