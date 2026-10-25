"use client";

import { useQuery } from "@tanstack/react-query";

import { InsightCard } from "@/components/dashboard/insight-card";
import { dashboardKeys, getInsights } from "@/lib/dashboard";

export function InsightsView() {
  const insights = useQuery({ queryKey: dashboardKeys.insights, queryFn: getInsights, staleTime: 0 });

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-xl font-semibold tracking-tight">Insights</h1>
        <p className="text-sm text-muted-foreground">
          Patterns across your applications, CV analyses, questions and learning plan. Each one shows the records it
          comes from and how many observations it rests on.
          {insights.data &&
            ` Below ${insights.data.minimum_observations} observations it's marked as not enough data: a single event isn't a pattern.`}{" "}
          Things that happened together aren&apos;t presented as cause and effect, and outcomes like rejections aren&apos;t
          used to judge your ability.
        </p>
      </div>

      {insights.isPending ? (
        <div aria-hidden className="h-40 animate-pulse rounded-xl bg-muted" />
      ) : insights.isError ? (
        <p role="alert" className="text-sm text-destructive">
          Insights couldn&apos;t be loaded.
        </p>
      ) : (
        <>
          {insights.data.insights.length === 0 ? (
            <p className="rounded-xl border border-dashed bg-background p-6 text-sm text-muted-foreground">
              No insights yet. They appear as your records grow.
            </p>
          ) : (
            <ul className="flex flex-col gap-3">
              {insights.data.insights.map((insight) => (
                <InsightCard key={insight.key} insight={insight} />
              ))}
            </ul>
          )}
          {insights.data.data_notes.length > 0 && (
            <section aria-labelledby="notes-heading" className="rounded-xl border bg-background p-4 text-sm">
              <h2 id="notes-heading" className="font-medium">
                For more insights
              </h2>
              <ul className="mt-2 list-disc pl-5 text-muted-foreground">
                {insights.data.data_notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}
