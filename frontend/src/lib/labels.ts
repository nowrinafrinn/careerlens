// Human-readable labels and badge colours for the API's enum values.

import type { Category, EvidenceStatus, Importance, Relevance, SelfReport } from "@/lib/analysis";
import type { ApplicationStatus, RoundResult, RoundStatus, RoundType } from "@/lib/applications";
import type { ParseStatus, SectionType } from "@/lib/cvs";
import type { Difficulty, PracticeStatus, ResponseQuality } from "@/lib/journals";
import type { AttemptOutcome, EvidenceBasis, GapStatus, GapType, Level, TaskStatus } from "@/lib/learning";
import type { SuggestionKind } from "@/lib/preparation";
import type { ChangeType, RecommendationKind } from "@/lib/recommendations";

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

export const EVIDENCE_STATUS: Record<EvidenceStatus, { label: string; tone: Tone; meaning: string }> = {
  demonstrated: {
    label: "Demonstrated",
    tone: "positive",
    meaning: "Your CV shows it being used, in a role, internship or project.",
  },
  partially_demonstrated: {
    label: "Partly shown",
    tone: "progress",
    meaning: "It's listed, or only something related is shown, or part of it is missing.",
  },
  not_found_in_cv: {
    label: "Not found in this CV",
    tone: "negative",
    meaning: "The CV doesn't mention it. That says nothing about whether you have it.",
  },
  needs_verification: {
    label: "Needs your judgement",
    tone: "muted",
    meaning: "Text matching can't decide this (soft skills, years, vague wording).",
  },
};

export const IMPORTANCE: Record<Importance, string> = {
  required: "Required",
  preferred: "Preferred",
  uncertain: "Importance unclear",
};

export const CATEGORY: Record<Category, string> = {
  technical_skill: "Technical skill",
  tool: "Tool or technology",
  experience: "Experience",
  education: "Education",
  project: "Projects",
  collaboration: "Collaboration",
  responsibility: "Responsibility",
  other: "Other",
};

export const SELF_REPORT: Record<SelfReport, string> = {
  unknown: "Not stated",
  have_not_on_cv: "I have this (not shown on my CV)",
  do_not_have: "I don't have this yet",
  learning: "I'm learning this",
};

export const RELEVANCE: Record<Relevance, string> = {
  direct: "Shown in use",
  listed: "Listed only",
  related: "Related skill",
  possible: "Possibly relevant",
};

export const RECOMMENDATION_KIND: Record<RecommendationKind, { label: string; tone: Tone; description: string }> = {
  presentation: {
    label: "Presentation",
    tone: "info",
    description: "You have relevant experience, but the CV could communicate it more clearly.",
  },
  unverified_claim: {
    label: "Unverified claim",
    tone: "progress",
    description: "A skill is named without anything in the CV to back it up.",
  },
  evidence_gap: {
    label: "Evidence gap",
    tone: "neutral",
    description: "The CV doesn't give enough to judge. You may well have the experience.",
  },
  potential_capability_gap: {
    label: "Possible learning goal",
    tone: "muted",
    description: "Only shown when you said you don't have something yet. No CV change; it's for your learning plan.",
  },
};

export const CHANGE_TYPE: Record<ChangeType, string> = {
  rewrite_passage: "Rewrite a bullet",
  add_bullet: "Add a bullet",
  remove_or_verify: "Remove or verify",
  no_cv_change: "No CV change",
};

export const RESPONSE_QUALITY: Record<ResponseQuality, { label: string; tone: Tone }> = {
  confident: { label: "Answered confidently", tone: "positive" },
  partial: { label: "Partly answered", tone: "progress" },
  could_not_answer: { label: "Couldn't answer", tone: "negative" },
  not_attempted: { label: "Not attempted", tone: "muted" },
};

export const PRACTICE_STATUS: Record<PracticeStatus, { label: string; tone: Tone }> = {
  new: { label: "Not reviewed", tone: "muted" },
  to_practice: { label: "To practise", tone: "progress" },
  practicing: { label: "Practising", tone: "info" },
  comfortable: { label: "Comfortable", tone: "positive" },
};

export const DIFFICULTY: Record<Difficulty, string> = {
  easy: "Easy",
  medium: "Medium",
  hard: "Hard",
  unknown: "Difficulty not set",
};

export const CONFIDENCE_LABELS: Record<number, string> = {
  1: "1 · Not at all",
  2: "2 · A little",
  3: "3 · Somewhat",
  4: "4 · Fairly",
  5: "5 · Very",
};

export const GAP_TYPE: Record<GapType, { label: string; description: string }> = {
  unclassified: { label: "Not classified yet", description: "Decide what kind of gap this is once you've looked at the evidence." },
  knowledge: { label: "Knowledge", description: "The underlying concept isn't understood yet." },
  application: { label: "Application", description: "You understand it but find it hard to apply." },
  speed: { label: "Speed", description: "You can solve it, but it takes too long." },
  recall: { label: "Recall", description: "You know it but can't retrieve it under pressure." },
  preparation: { label: "Preparation", description: "You need structured practice." },
  communication: { label: "Communication", description: "You find it hard to explain an answer or experience clearly." },
};

export const GAP_STATUS: Record<GapStatus, { label: string; tone: Tone }> = {
  open: { label: "Open", tone: "progress" },
  improving: { label: "Improving", tone: "info" },
  resolved: { label: "Resolved", tone: "positive" },
  dismissed: { label: "Dismissed", tone: "muted" },
};

export const LEVEL: Record<Level, string> = { low: "Low", medium: "Medium", high: "High" };

export const EVIDENCE_BASIS: Record<EvidenceBasis, string> = {
  user_confirmed: "Your own statement",
  recorded_outcome: "Recorded outcome",
  interviewer_feedback: "Interviewer feedback",
  user_interpretation: "Your interpretation",
  hypothesis: "Unconfirmed inference",
};

export const TASK_STATUS: Record<TaskStatus, { label: string; tone: Tone }> = {
  planned: { label: "Planned", tone: "muted" },
  in_progress: { label: "In progress", tone: "info" },
  completed: { label: "Completed", tone: "positive" },
  needs_more_practice: { label: "Needs more practice", tone: "progress" },
};

export const ATTEMPT_OUTCOME: Record<AttemptOutcome, string> = {
  struggled: "Struggled",
  partial: "Partly there",
  solid: "Solid",
};

export const SUGGESTION_KIND: Record<SuggestionKind, { label: string; order: number }> = {
  round_format: { label: "The round itself", order: 0 },
  project_question: { label: "Explaining your own work", order: 1 },
  review_topic: { label: "Topics to review", order: 2 },
  challenging_area: { label: "Harder areas: prepare honest answers", order: 3 },
  behavioral_question: { label: "Behavioural practice (STAR)", order: 4 },
  gap_practice: { label: "From your learning plan", order: 5 },
  revisit_question: { label: "From your question bank", order: 6 },
  practice_question: { label: "Practice questions", order: 7 },
};

export const SECTION_TYPE: Record<SectionType, string> = {
  header: "Name and contact",
  summary: "Summary",
  education: "Education",
  skills: "Skills",
  experience: "Work experience",
  internship: "Internships",
  projects: "Projects",
  certifications: "Certifications and courses",
  achievements: "Achievements",
  other_experience: "Other relevant experience",
  other: "Other",
  unrecognized: "Unrecognized",
};

export const PARSE_STATUS: Record<ParseStatus, { label: string; tone: Tone; description: string }> = {
  ok: { label: "Read successfully", tone: "positive", description: "Sections were recognized. Check them anyway." },
  partial: {
    label: "Partly recognized",
    tone: "progress",
    description: "Some text couldn't be placed in a section. Review the blocks below.",
  },
  failed: { label: "Couldn't be read", tone: "negative", description: "Almost no text could be extracted." },
};

export const ROUND_RESULT: Record<RoundResult, { label: string; tone: Tone }> = {
  unknown: { label: "Result unknown", tone: "muted" },
  passed: { label: "Passed", tone: "positive" },
  failed: { label: "Not passed", tone: "negative" },
  not_applicable: { label: "No result", tone: "muted" },
};
