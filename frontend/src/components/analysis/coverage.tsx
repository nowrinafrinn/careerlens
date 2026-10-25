import type { Analysis } from "@/lib/analysis";

type Coverage = Analysis["coverage"];

const SEGMENTS = [
  { key: "demonstrated", label: "demonstrated", className: "bg-emerald-500" },
  { key: "partially_demonstrated", label: "partly shown", className: "bg-amber-400" },
  { key: "not_found_in_cv", label: "not found in this CV", className: "bg-rose-400" },
  { key: "needs_verification", label: "need your judgement", className: "bg-muted-foreground/40" },
] as const;

/** A stacked bar of the required requirements by evidence status, with a text equivalent. */
export function CoverageBar({ coverage }: { coverage: Coverage }) {
  if (coverage.required_total === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No requirements were marked as required in this posting, so there&apos;s no coverage figure. See each
        requirement below.
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm">
        <span className="text-2xl font-semibold tabular-nums">
          {coverage.demonstrated} of {coverage.required_total}
        </span>{" "}
        required requirements are visibly demonstrated by your CV
        <span className="text-muted-foreground"> ({coverage.percent}%)</span>
      </p>
      <div
        className="flex h-2.5 w-full overflow-hidden rounded-full bg-muted"
        role="img"
        aria-label={SEGMENTS.map((s) => `${coverage[s.key]} ${s.label}`).join(", ")}
      >
        {SEGMENTS.map((segment) =>
          coverage[segment.key] > 0 ? (
            <div
              key={segment.key}
              className={segment.className}
              style={{ width: `${(100 * coverage[segment.key]) / coverage.required_total}%` }}
            />
          ) : null,
        )}
      </div>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        {SEGMENTS.map((segment) => (
          <li key={segment.key} className="flex items-center gap-1.5 tabular-nums">
            <span aria-hidden className={`size-2 rounded-full ${segment.className}`} />
            {coverage[segment.key]} {segment.label}
          </li>
        ))}
      </ul>
    </div>
  );
}
