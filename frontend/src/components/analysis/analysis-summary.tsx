"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { CoverageBar } from "@/components/analysis/coverage";
import { analysisKeys, getLatestAnalysis } from "@/lib/analysis";
import type { ApplicationDetail } from "@/lib/applications";
import { buttonClass } from "@/lib/button-class";

/** The application page's entry point to the requirement analysis. */
export function AnalysisSummary({ application }: { application: ApplicationDetail }) {
  const ready = Boolean(application.job_description?.trim()) && Boolean(application.cv_version);
  const { data: analysis, isPending } = useQuery({
    queryKey: analysisKeys.latest(application.id),
    queryFn: () => getLatestAnalysis(application.id),
    enabled: ready,
  });
  const href = `/applications/${application.id}/analysis`;

  return (
    <section aria-labelledby="evidence-heading" className="flex flex-col gap-3">
      <h2 id="evidence-heading" className="text-base font-semibold">
        Requirements and CV evidence
      </h2>
      <div className="flex flex-col gap-4 surface rounded-xl border p-4">
        {!ready ? (
          <p className="text-sm text-muted-foreground">
            {!application.job_description?.trim() && !application.cv_version
              ? "Add the job description and choose a CV version to compare them."
              : !application.job_description?.trim()
                ? "Add the job description to compare it with your CV."
                : "Choose which CV version you used to compare it with the job description."}{" "}
            <Link href={`/applications/${application.id}/edit`} className="text-foreground underline underline-offset-4">
              Edit details
            </Link>
          </p>
        ) : isPending ? (
          <div aria-hidden className="h-12 animate-pulse rounded bg-muted" />
        ) : !analysis ? (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground">
              See which of the job&apos;s requirements your CV demonstrates, and where.
            </p>
            <Link href={href} className={buttonClass({ size: "sm" })}>
              Analyse requirements
            </Link>
          </div>
        ) : (
          <>
            <CoverageBar coverage={analysis.coverage} />
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-muted-foreground">
                {analysis.is_stale
                  ? "Out of date: the job description or CV changed since it was run."
                  : `${analysis.requirements.length} requirements checked against CV v${analysis.cv_version.version_number}.`}
              </p>
              <div className="flex flex-wrap gap-2">
                <Link
                  href={`/applications/${application.id}/cv-suggestions`}
                  className={buttonClass({ variant: "outline", size: "sm" })}
                >
                  CV suggestions
                </Link>
                <Link href={href} className={buttonClass({ variant: "outline", size: "sm" })}>
                  Open analysis
                </Link>
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
