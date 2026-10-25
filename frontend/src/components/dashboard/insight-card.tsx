import Link from "next/link";

import { Pill } from "@/components/applications/status-badge";
import { INSIGHT_BASIS, sourceHref, type Insight } from "@/lib/dashboard";

export function InsightCard({ insight, compact = false }: { insight: Insight; compact?: boolean }) {
  return (
    <li className={`flex flex-col gap-2 surface rounded-xl border p-4 text-sm ${insight.sufficient_data ? "" : "border-dashed"}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="min-w-0 font-medium">{insight.title}</p>
        <div className="flex flex-wrap gap-1.5">
          {!insight.sufficient_data && <Pill tone="muted">Not enough data yet</Pill>}
          <Pill tone="neutral">
            {`${insight.observation_count} observation${insight.observation_count === 1 ? "" : "s"}`}
          </Pill>
        </div>
      </div>
      <p>{insight.statement}</p>
      {!compact && (
        <>
          <p className="text-xs text-muted-foreground">
            <span className="font-medium text-foreground">{INSIGHT_BASIS[insight.basis]}.</span> {insight.caveat}
          </p>
          <div className="text-xs text-muted-foreground">
            <span className="font-medium text-foreground">Based on: </span>
            {insight.sources.map((source, index) => {
              const href = sourceHref(source);
              return (
                <span key={`${source.kind}-${source.id}`}>
                  {index > 0 && " · "}
                  {href ? (
                    <Link href={href} className="underline underline-offset-4">
                      {source.label}
                    </Link>
                  ) : (
                    source.label
                  )}
                </span>
              );
            })}
          </div>
        </>
      )}
    </li>
  );
}
