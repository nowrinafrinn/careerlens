"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Pill } from "@/components/applications/status-badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import { decideRecommendation, recommendationKeys, type Decision, type Recommendation } from "@/lib/recommendations";
import { CHANGE_TYPE, RECOMMENDATION_KIND } from "@/lib/labels";

/** Shows "[gaps]" as visibly unfinished, so they can't be pasted into a CV by accident. */
export function WithGaps({ text }: { text: string }) {
  return (
    <>
      {text.split(/(\[[^\]]+\])/).map((part, index) =>
        part.startsWith("[") && part.endsWith("]") ? (
          <mark
            key={index}
            className="rounded bg-amber-100 px-0.5 text-amber-900 dark:bg-amber-950 dark:text-amber-200"
          >
            {part}
          </mark>
        ) : (
          <span key={index}>{part}</span>
        ),
      )}
    </>
  );
}

export function RecommendationCard({ rec, analysisId }: { rec: Recommendation; analysisId: string }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(rec.final_text ?? rec.suggested_text ?? rec.original_text ?? "");
  const mutation = useMutation({
    mutationFn: (body: Decision) => decideRecommendation(rec.id, body),
    onSuccess: (updated) => {
      queryClient.setQueryData<Recommendation[]>(recommendationKeys.forAnalysis(analysisId), (items) =>
        items?.map((item) => (item.id === updated.id ? updated : item)),
      );
      setEditing(false);
    },
  });
  const kind = RECOMMENDATION_KIND[rec.kind];
  const decided = rec.status !== "proposed";
  const usable = rec.change_type !== "no_cv_change";

  return (
    <li className={`flex flex-col gap-3 rounded-xl border bg-background p-4 ${rec.status === "rejected" ? "opacity-60" : ""}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="font-medium">{rec.title}</h3>
          <p className="text-xs text-muted-foreground">For the requirement: “{rec.requirement_text}”</p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Pill tone={kind.tone}>{kind.label}</Pill>
          <Pill tone="muted">{CHANGE_TYPE[rec.change_type]}</Pill>
        </div>
      </div>

      <p className="text-sm">{rec.rationale}</p>

      {rec.original_text && (
        <div className="text-sm">
          <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            {rec.change_type === "add_bullet" ? "Related text in your CV" : "Your CV now"}
          </p>
          <blockquote className="mt-1 border-l-2 pl-3 whitespace-pre-line text-muted-foreground">{rec.original_text}</blockquote>
        </div>
      )}

      {rec.suggested_text && !decided && !editing && (
        <div className="text-sm">
          <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            {rec.change_type === "add_bullet" ? "A bullet to complete" : "Suggested version"}
          </p>
          <p className="mt-1 rounded-lg bg-muted/60 px-3 py-2">
            <WithGaps text={rec.suggested_text} />
          </p>
        </div>
      )}

      {rec.assumptions.length > 0 && !decided && (
        <div className="text-sm">
          <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Before you use this, confirm</p>
          <ul className="mt-1 list-disc pl-5 text-muted-foreground">
            {rec.assumptions.map((assumption) => (
              <li key={assumption}>{assumption}</li>
            ))}
          </ul>
        </div>
      )}

      {editing && (
        <div className="flex flex-col gap-2">
          <label htmlFor={`edit-${rec.id}`} className="text-sm font-medium">
            Your version
          </label>
          <Textarea
            id={`edit-${rec.id}`}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            rows={3}
            maxLength={2000}
            aria-describedby={`edit-${rec.id}-hint`}
          />
          <p id={`edit-${rec.id}-hint`} className="text-xs text-muted-foreground">
            Replace every [gap] with what really happened, or remove it.
          </p>
        </div>
      )}

      {decided && (
        <div className="text-sm">
          <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            {rec.status === "rejected" ? "Rejected" : rec.status === "edited" ? "Your version" : "Accepted"}
          </p>
          {rec.final_text && (
            <p className="mt-1 rounded-lg bg-muted/60 px-3 py-2">
              <WithGaps text={rec.final_text} />
            </p>
          )}
        </div>
      )}

      {rec.number_warnings.length > 0 && (
        <p role="note" className="text-sm text-amber-800 dark:text-amber-300">
          Check {rec.number_warnings.length === 1 ? "this number" : "these numbers"}:{" "}
          {rec.number_warnings.join(", ")}. {rec.number_warnings.length === 1 ? "It isn't" : "They aren't"} in your
          original text. Only keep figures you can back up.
        </p>
      )}

      {mutation.isError && (
        <p role="alert" className="text-sm text-destructive">
          {mutation.error instanceof ApiError ? mutation.error.message : "The change couldn't be saved."}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        {editing ? (
          <>
            <Button size="sm" onClick={() => mutation.mutate({ status: "edited", final_text: draft })} disabled={mutation.isPending}>
              Save my version
            </Button>
            <Button size="sm" variant="outline" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </>
        ) : decided ? (
          <Button size="sm" variant="outline" onClick={() => mutation.mutate({ status: "proposed" })} disabled={mutation.isPending}>
            Undo
          </Button>
        ) : (
          <>
            <Button size="sm" onClick={() => mutation.mutate({ status: "accepted" })} disabled={mutation.isPending}>
              {usable ? "Accept" : "Noted"}
            </Button>
            {usable && (
              <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
                Edit
              </Button>
            )}
            <Button
              size="sm"
              variant="ghost"
              className="text-muted-foreground"
              onClick={() => mutation.mutate({ status: "rejected" })}
              disabled={mutation.isPending}
            >
              {usable ? "Reject" : "Not relevant"}
            </Button>
          </>
        )}
      </div>
    </li>
  );
}
