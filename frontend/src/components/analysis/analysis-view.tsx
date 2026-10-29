"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";

import { AnalyseWithAI } from "@/components/analysis/analyse-with-ai";
import { CoverageBar } from "@/components/analysis/coverage";
import { RequirementCard } from "@/components/analysis/requirement-card";
import { Button } from "@/components/ui/button";
import { LoadError } from "@/components/load-error";
import { ApiError } from "@/lib/api";
import { analysisKeys, getLatestAnalysis, runAnalysis, type Requirement } from "@/lib/analysis";
import { applicationKeys, getApplication } from "@/lib/applications";
import { buttonClass } from "@/lib/button-class";
import { formatDateTime } from "@/lib/format";
import { EVIDENCE_STATUS } from "@/lib/labels";

const GROUPS: { title: string; description: string; filter: (r: Requirement) => boolean }[] = [
  {
    title: "Required",
    description: "Listed as requirements, or worded as a must.",
    filter: (r) => !r.dismissed && r.category !== "responsibility" && r.importance === "required",
  },
  {
    title: "Preferred",
    description: "Nice to have, a plus, or listed under preferred qualifications.",
    filter: (r) => !r.dismissed && r.category !== "responsibility" && r.importance === "preferred",
  },
  {
    title: "Importance unclear",
    description: "The posting doesn't say whether these are required. Set it if you know.",
    filter: (r) => !r.dismissed && r.category !== "responsibility" && r.importance === "uncertain",
  },
  {
    title: "Responsibilities",
    description: "What the job involves. Useful for interview preparation; not counted in coverage.",
    filter: (r) => !r.dismissed && r.category === "responsibility",
  },
  {
    title: "Dismissed",
    description: "Lines you marked as not real requirements. Kept, but left out of coverage.",
    filter: (r) => r.dismissed,
  },
];

export function AnalysisView() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const application = useQuery({ queryKey: applicationKeys.detail(id), queryFn: () => getApplication(id) });
  const analysis = useQuery({ queryKey: analysisKeys.latest(id), queryFn: () => getLatestAnalysis(id) });
  const run = useMutation({
    mutationFn: () => runAnalysis(id),
    onSuccess: (result) => queryClient.setQueryData(analysisKeys.latest(id), result),
  });

  if (application.isPending || analysis.isPending) {
    return <div aria-hidden className="h-64 animate-pulse rounded-xl bg-muted" />;
  }
  if (application.isError) {
    return <LoadError error={application.error} thing="Application" backHref="/applications" backLabel="Back to applications" />;
  }
  if (analysis.isError) {
    return <LoadError error={analysis.error} thing="Analysis" backHref={`/applications/${id}`} backLabel="Back to the application" />;
  }

  const app = application.data;
  const result = analysis.data;
  const runError = run.error instanceof ApiError ? run.error.message : run.isError ? "The analysis failed." : null;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <Link href={`/applications/${id}`} className="tap self-start text-sm text-muted-foreground hover:text-foreground">
          ← {app.position_title}, {app.company_name}
        </Link>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex flex-col gap-1">
            <h1 className="text-2xl font-semibold tracking-tight">Requirements and CV evidence</h1>
            {result && (
              <p className="text-sm text-muted-foreground">
                Compared with CV v{result.cv_version.version_number} · {result.cv_version.label} · analysed{" "}
                {formatDateTime(result.created_at)} ·{" "}
                {result.method === "ai"
                  ? "AI-assisted, every citation checked against your CV"
                  : "rule-based, nothing sent to an AI service"}
              </p>
            )}
          </div>
          {result && (
            <div className="flex flex-wrap items-start gap-2">
              <Link href={`/applications/${id}/cv-suggestions`} className={buttonClass({ size: "sm" })}>
                CV suggestions
              </Link>
              <Button
                variant="outline"
                size="sm"
                onClick={() => run.mutate()}
                disabled={run.isPending}
              >
                {run.isPending ? "Analysing…" : "Run again"}
              </Button>
              <AnalyseWithAI applicationId={id} />
            </div>
          )}
        </div>
      </div>

      {runError && (
        <p role="alert" className="text-sm text-destructive">
          {runError}
        </p>
      )}

      {!result ? (
        <div className="flex flex-col items-start gap-3 surface rounded-xl border border-dashed p-6">
          <p className="font-medium">Not analysed yet</p>
          <p className="max-w-xl text-sm text-muted-foreground">
            CareerLens will pick out the job&apos;s requirements and look for evidence of each one in the CV version
            this application uses. Your input on the results is kept if you run it again later.
          </p>
          <div className="flex flex-wrap items-start gap-2">
            <Button onClick={() => run.mutate()} disabled={run.isPending}>
              {run.isPending ? "Analysing…" : "Analyse requirements"}
            </Button>
            <AnalyseWithAI applicationId={id} />
          </div>
        </div>
      ) : (
        <>
          {result.is_stale && (
            <div role="status" className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm dark:border-amber-800 dark:bg-amber-950">
              <p className="font-medium">This analysis is out of date.</p>
              <ul className="mt-1 list-disc pl-5">
                {result.stale_reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
              <p className="mt-1">Run it again to see current results. Your own assessments will be carried over.</p>
            </div>
          )}

          {result.notes.length > 0 && (
            <section aria-labelledby="notes-heading" className="flex flex-col gap-1.5 surface rounded-xl border p-4 text-sm">
              <h2 id="notes-heading" className="font-medium">
                How this analysis was made
              </h2>
              <ul className="flex list-disc flex-col gap-1 pl-5 text-muted-foreground">
                {result.notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </section>
          )}

          <section aria-labelledby="coverage-heading" className="flex flex-col gap-4 surface rounded-xl border p-5">
            <h2 id="coverage-heading" className="sr-only">
              Coverage
            </h2>
            <CoverageBar coverage={result.coverage} />
            <details className="text-sm text-muted-foreground">
              <summary className="tap cursor-pointer text-foreground">How to read this</summary>
              <p className="mt-2">{result.coverage.explanation}</p>
              <dl className="mt-3 grid gap-x-4 gap-y-1.5 sm:grid-cols-[auto_1fr]">
                {Object.values(EVIDENCE_STATUS).map((status) => (
                  <div key={status.label} className="contents">
                    <dt className="font-medium text-foreground">{status.label}</dt>
                    <dd>{status.meaning}</dd>
                  </div>
                ))}
              </dl>
            </details>
          </section>

          {result.requirements.length === 0 ? (
            <p className="surface rounded-xl border border-dashed p-6 text-sm text-muted-foreground">
              No requirements could be picked out of this job description. Postings that use headings such as
              &quot;Requirements&quot; or bullet points work best.
            </p>
          ) : (
            GROUPS.map((group) => {
              const items = result.requirements.filter(group.filter);
              if (items.length === 0) return null;
              return (
                <section key={group.title} aria-labelledby={`group-${group.title}`} className="flex flex-col gap-3">
                  <div>
                    <h2 id={`group-${group.title}`} className="text-base font-semibold">
                      {group.title} <span className="font-normal text-muted-foreground tabular-nums">({items.length})</span>
                    </h2>
                    <p className="text-sm text-muted-foreground">{group.description}</p>
                  </div>
                  <ul className="flex flex-col gap-2">
                    {items.map((requirement) => (
                      <RequirementCard key={requirement.id} requirement={requirement} applicationId={id} />
                    ))}
                  </ul>
                </section>
              );
            })
          )}
        </>
      )}
      {app.cv_version && (
        <p className="text-xs text-muted-foreground">
          Does a verdict look wrong because a CV section was misread?{" "}
          <Link href={`/cvs/${app.cv_version.id}`} className={buttonClass({ variant: "link", size: "sm" }, "px-0")}>
            Check how your CV was read
          </Link>
        </p>
      )}
    </div>
  );
}
