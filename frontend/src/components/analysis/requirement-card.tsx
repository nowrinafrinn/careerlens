"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Pill } from "@/components/applications/status-badge";
import { AddToPlan } from "@/components/learning/add-to-plan";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import {
  analysisKeys,
  updateRequirement,
  type Importance,
  type Requirement,
  type RequirementUpdate,
  type SelfReport,
} from "@/lib/analysis";
import { CATEGORY, EVIDENCE_STATUS, IMPORTANCE, RELEVANCE, SECTION_TYPE, SELF_REPORT } from "@/lib/labels";
import { gapFromRequirement } from "@/lib/learning";

export function RequirementCard({ requirement, applicationId }: { requirement: Requirement; applicationId: string }) {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: (body: RequirementUpdate) => updateRequirement(requirement.id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: analysisKeys.latest(applicationId) });
      // A new self-report changes which CV suggestions apply.
      queryClient.invalidateQueries({ queryKey: ["applications", "recommendations"] });
    },
  });
  const status = EVIDENCE_STATUS[requirement.evidence_status];
  const id = requirement.id;

  return (
    <li className={`surface rounded-xl border ${requirement.dismissed ? "opacity-60" : ""}`}>
      <details className="group">
        <summary className="flex cursor-pointer list-none items-start gap-3 p-4 [&::-webkit-details-marker]:hidden">
          <span
            aria-hidden
            className="mt-0.5 text-muted-foreground transition-transform group-open:rotate-90"
          >
            ›
          </span>
          <div className="flex min-w-0 flex-1 flex-col gap-1.5">
            <p className="text-sm">{requirement.text}</p>
            <div className="flex flex-wrap items-center gap-1.5">
              <Pill tone={status.tone}>{status.label}</Pill>
              <span className="text-xs text-muted-foreground">{CATEGORY[requirement.category]}</span>
              {requirement.self_report !== "unknown" && (
                <span className="text-xs text-muted-foreground">· You: {SELF_REPORT[requirement.self_report]}</span>
              )}
            </div>
          </div>
        </summary>

        <div className="flex flex-col gap-4 border-t px-4 pt-3 pb-4 text-sm sm:pl-10">
          <div className="flex flex-col gap-1">
            <h4 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">What the CV shows</h4>
            <p>{requirement.evidence_rationale}</p>
            {requirement.missing_details && <p className="text-muted-foreground">{requirement.missing_details}</p>}
          </div>

          {requirement.evidence.length > 0 && (
            <div className="flex flex-col gap-2">
              <h4 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                CV passages used
              </h4>
              <ul className="flex flex-col gap-2">
                {requirement.evidence.map((link) => (
                  <li key={link.passage_id} className="rounded-lg bg-muted/60 px-3 py-2">
                    <blockquote className="whitespace-pre-line">{link.passage_text}</blockquote>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {RELEVANCE[link.relevance]} · from {SECTION_TYPE[link.section_type].toLowerCase()} · {link.note}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex flex-col gap-1">
            <h4 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Suggested next step</h4>
            <p>{requirement.suggested_action}</p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <label htmlFor={`self-${id}`} className="text-sm font-medium">
                Your own assessment
              </label>
              <NativeSelect
                id={`self-${id}`}
                value={requirement.self_report}
                disabled={mutation.isPending}
                onChange={(event) => mutation.mutate({ self_report: event.target.value as SelfReport })}
                aria-describedby={`self-${id}-hint`}
              >
                {Object.entries(SELF_REPORT).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </NativeSelect>
              <p id={`self-${id}-hint`} className="text-xs text-muted-foreground">
                Stored next to the CV verdict. It doesn&apos;t change what the CV shows.
              </p>
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor={`importance-${id}`} className="text-sm font-medium">
                Importance
              </label>
              <NativeSelect
                id={`importance-${id}`}
                value={requirement.importance}
                disabled={mutation.isPending}
                onChange={(event) => mutation.mutate({ importance: event.target.value as Importance })}
                aria-describedby={`importance-${id}-hint`}
              >
                {Object.entries(IMPORTANCE).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </NativeSelect>
              <p id={`importance-${id}-hint`} className="text-xs text-muted-foreground">
                {requirement.user_edited ? "Changed by you." : "Read from the posting. Correct it if it's wrong."}
              </p>
            </div>
          </div>

          {(requirement.self_report === "do_not_have" || requirement.self_report === "learning") && (
            <div className="flex flex-col gap-1.5 rounded-lg bg-muted/60 px-3 py-2">
              <p className="text-sm">
                You said {requirement.self_report === "learning" ? "you're learning this" : "you don't have this yet"}.{" "}
                {requirement.skill_gap_id
                  ? "It's in your learning plan, where you can track practice and progress."
                  : "Add it to your learning plan to track practice and progress."}
              </p>
              <AddToPlan
                existingGapId={requirement.skill_gap_id}
                skillOptions={requirement.terms}
                add={(skill) => gapFromRequirement(requirement.id, skill)}
                refresh={[[...analysisKeys.latest(applicationId)]]}
              />
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-muted-foreground">
              {requirement.terms.length > 0
                ? `Matched terms: ${requirement.terms.join(", ")}${requirement.match_mode === "any" ? " (any one is enough)" : ""}`
                : "No known skill terms in this line."}
            </p>
            <Button
              variant="ghost"
              size="sm"
              className="text-muted-foreground"
              disabled={mutation.isPending}
              onClick={() => mutation.mutate({ dismissed: !requirement.dismissed })}
            >
              {requirement.dismissed ? "Restore this requirement" : "Not a real requirement"}
            </Button>
          </div>
          {mutation.isError && (
            <p role="alert" className="text-sm text-destructive">
              The change couldn&apos;t be saved. Try again.
            </p>
          )}
        </div>
      </details>
    </li>
  );
}
