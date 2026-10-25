import { cn } from "cn";

import type { ApplicationStatus, RoundResult, RoundStatus } from "@/lib/applications";
import { APPLICATION_STATUS, ROUND_RESULT, ROUND_STATUS, TONE_CLASSES } from "@/lib/labels";

export function Pill({ tone, children, className }: { tone: keyof typeof TONE_CLASSES; children: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex h-5 shrink-0 items-center rounded-full px-2 text-xs font-medium whitespace-nowrap",
        TONE_CLASSES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function ApplicationStatusBadge({ status }: { status: ApplicationStatus }) {
  const meta = APPLICATION_STATUS[status];
  return <Pill tone={meta.tone}>{meta.label}</Pill>;
}

export function RoundStatusBadge({ status }: { status: RoundStatus }) {
  const meta = ROUND_STATUS[status];
  return <Pill tone={meta.tone}>{meta.label}</Pill>;
}

export function RoundResultBadge({ result }: { result: RoundResult }) {
  const meta = ROUND_RESULT[result];
  return <Pill tone={meta.tone}>{meta.label}</Pill>;
}
