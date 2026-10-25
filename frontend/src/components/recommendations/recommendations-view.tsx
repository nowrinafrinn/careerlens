"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { RecommendationCard, WithGaps } from "@/components/recommendations/recommendation-card";
import { Button } from "@/components/ui/button";
import { analysisKeys, getLatestAnalysis } from "@/lib/analysis";
import { applicationKeys, getApplication } from "@/lib/applications";
import { buttonClass } from "@/lib/button-class";
import { RECOMMENDATION_KIND } from "@/lib/labels";
import { listRecommendations, recommendationKeys, type RecommendationKind } from "@/lib/recommendations";

const ORDER: RecommendationKind[] = ["presentation", "unverified_claim", "evidence_gap", "potential_capability_gap"];

export function RecommendationsView() {
  const { id } = useParams<{ id: string }>();
  const application = useQuery({ queryKey: applicationKeys.detail(id), queryFn: () => getApplication(id) });
  const analysis = useQuery({ queryKey: analysisKeys.latest(id), queryFn: () => getLatestAnalysis(id) });
  const analysisId = analysis.data?.id;
  const recs = useQuery({
    queryKey: recommendationKeys.forAnalysis(analysisId ?? "none"),
    queryFn: () => listRecommendations(analysisId!),
    enabled: Boolean(analysisId),
  });

  if (application.isPending || analysis.isPending || (analysisId && recs.isPending)) {
    return <div aria-hidden className="h-64 animate-pulse rounded-xl bg-muted" />;
  }
  if (application.isError || analysis.isError || recs.isError) {
    return (
      <p role="alert" className="text-sm text-destructive">
        Suggestions couldn&apos;t be loaded. Check that the backend is running, then refresh.
      </p>
    );
  }

  const app = application.data;
  const items = recs.data ?? [];
  const toApply = items.filter((r) => (r.status === "accepted" || r.status === "edited") && r.final_text);
  const open = items.filter((r) => r.status === "proposed").length;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <Link href={`/applications/${id}`} className="text-sm text-muted-foreground hover:text-foreground">
          ← {app.position_title}, {app.company_name}
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">CV suggestions</h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Ways to show your real experience more clearly for this job, based on the{" "}
          <Link href={`/applications/${id}/analysis`} className="text-foreground underline underline-offset-4">
            requirement analysis
          </Link>
          . Nothing here invents experience or results: text in [brackets] is for you to fill in truthfully or
          delete. Your uploaded CV is never changed; copy what you accept into your own document.
        </p>
      </div>

      {!analysis.data ? (
        <div className="flex flex-col items-start gap-3 rounded-xl border border-dashed bg-background p-6">
          <p className="font-medium">No analysis yet</p>
          <p className="text-sm text-muted-foreground">Suggestions come from the requirement analysis. Run it first.</p>
          <Link href={`/applications/${id}/analysis`} className={buttonClass({ size: "sm" })}>
            Go to the analysis
          </Link>
        </div>
      ) : (
        <>
          {analysis.data.is_stale && (
            <p role="status" className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm dark:border-amber-800 dark:bg-amber-950">
              The analysis these come from is out of date.{" "}
              <Link href={`/applications/${id}/analysis`} className="font-medium underline underline-offset-4">
                Run it again
              </Link>{" "}
              for current suggestions. Your decisions will be kept.
            </p>
          )}

          <p className="text-sm text-muted-foreground tabular-nums" aria-live="polite">
            {items.length === 0
              ? "This analysis has no suggestions. If it was run before CV suggestions existed, run it again."
              : `${open} of ${items.length} suggestions still to decide.`}
          </p>

          {toApply.length > 0 && <ToApply texts={toApply.map((r) => r.final_text!)} />}

          {ORDER.map((kind) => {
            const group = items.filter((r) => r.kind === kind);
            if (group.length === 0) return null;
            return (
              <section key={kind} aria-labelledby={`kind-${kind}`} className="flex flex-col gap-3">
                <div>
                  <h2 id={`kind-${kind}`} className="text-base font-semibold">
                    {RECOMMENDATION_KIND[kind].label}{" "}
                    <span className="font-normal text-muted-foreground tabular-nums">({group.length})</span>
                  </h2>
                  <p className="text-sm text-muted-foreground">{RECOMMENDATION_KIND[kind].description}</p>
                </div>
                <ul className="flex flex-col gap-3">
                  {group.map((rec) => (
                    <RecommendationCard key={rec.id} rec={rec} analysisId={analysis.data!.id} />
                  ))}
                </ul>
              </section>
            );
          })}
        </>
      )}
    </div>
  );
}

function ToApply({ texts }: { texts: string[] }) {
  const [copied, setCopied] = useState(false);
  const unfinished = texts.some((text) => /\[[^\]]+\]/.test(text));

  async function copy() {
    try {
      await navigator.clipboard.writeText(texts.join("\n"));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  return (
    <section aria-labelledby="apply-heading" className="flex flex-col gap-3 rounded-xl border bg-background p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="apply-heading" className="text-base font-semibold">
          To apply in your CV <span className="font-normal text-muted-foreground tabular-nums">({texts.length})</span>
        </h2>
        <Button size="sm" variant="outline" onClick={copy}>
          {copied ? "Copied" : "Copy all"}
        </Button>
      </div>
      {unfinished && (
        <p className="text-sm text-amber-800 dark:text-amber-300">
          Some lines still contain [gaps]. Fill them in or remove them before using the text.
        </p>
      )}
      <ul className="flex list-disc flex-col gap-1.5 pl-5 text-sm">
        {texts.map((text, index) => (
          <li key={index}>
            <WithGaps text={text} />
          </li>
        ))}
      </ul>
    </section>
  );
}
