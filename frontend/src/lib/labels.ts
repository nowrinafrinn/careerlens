// Human-readable labels and badge colours for the API's enum values.

import type { ApplicationStatus, RoundResult, RoundStatus, RoundType } from "@/lib/applications";

type Tone = "neutral" | "info" | "progress" | "positive" | "negative" | "muted";

export const TONE_CLASSES: Record<Tone, string> = {
  neutral: "bg-secondary text-secondary-foreground",
  info: "bg-sky-100 text-sky-900 dark:bg-sky-950 dark:text-sky-200",
  progress: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200",
  positive: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200",
  negative: "bg-rose-100 text-rose-900 dark:bg-rose-950 dark:text-rose-200",
  muted: "bg-muted text-muted-foreground",
};

export const APPLICATION_STATUS: Record<ApplicationStatus, { label: string; tone: Tone }> = {
  interested: { label: "Interested", tone: "neutral" },
  preparing: { label: "Preparing to apply", tone: "info" },
  applied: { label: "Applied", tone: "info" },
  in_progress: { label: "In progress", tone: "progress" },
  offer: { label: "Offer received", tone: "positive" },
  rejected: { label: "Rejected", tone: "negative" },
  withdrawn: { label: "Withdrawn", tone: "muted" },
  closed_unknown: { label: "Closed, outcome unknown", tone: "muted" },
};

export const APPLICATION_STATUS_ORDER = Object.keys(APPLICATION_STATUS) as ApplicationStatus[];

export const ROUND_TYPE: Record<RoundType, string> = {
  cv_screening: "CV screening",
  online_assessment: "Online assessment",
  written_exam: "Written exam",
  technical_interview: "Technical interview",
  hr_interview: "HR interview",
  managerial_interview: "Managerial interview",
  final_decision: "Final decision",
  other: "Other",
};

export const ROUND_STATUS: Record<RoundStatus, { label: string; tone: Tone }> = {
  not_scheduled: { label: "Not scheduled", tone: "muted" },
  upcoming: { label: "Upcoming", tone: "info" },
  preparing: { label: "Preparing", tone: "info" },
  completed: { label: "Completed", tone: "neutral" },
  awaiting_result: { label: "Awaiting result", tone: "progress" },
  rescheduled: { label: "Rescheduled", tone: "progress" },
  cancelled: { label: "Cancelled", tone: "muted" },
};

export const ROUND_RESULT: Record<RoundResult, { label: string; tone: Tone }> = {
  unknown: { label: "Result unknown", tone: "muted" },
  passed: { label: "Passed", tone: "positive" },
  failed: { label: "Not passed", tone: "negative" },
  not_applicable: { label: "No result", tone: "muted" },
};
