"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import { ApiError } from "@/lib/api";
import { buttonClass } from "@/lib/button-class";
import { learningKeys, type GapDetail } from "@/lib/learning";

type Props = {
  /** The gap this source already feeds, if any. */
  existingGapId: string | null | undefined;
  /** Skill names to choose from (e.g. a requirement's terms). Empty = use the default on the server. */
  skillOptions: string[];
  add: (skillName?: string) => Promise<GapDetail>;
  /** Extra query keys to refresh afterwards (the analysis or question that now links to the gap). */
  refresh: readonly unknown[][];
};

/** "Add to learning plan", or a link once the source already feeds a gap. */
export function AddToPlan({ existingGapId, skillOptions, add, refresh }: Props) {
  const queryClient = useQueryClient();
  const [skill, setSkill] = useState(skillOptions[0] ?? "");
  const [created, setCreated] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: () => add(skill || undefined),
    onSuccess: (gap) => {
      setCreated(gap.id);
      queryClient.invalidateQueries({ queryKey: learningKeys.all });
      for (const key of refresh) queryClient.invalidateQueries({ queryKey: key });
    },
  });
  const gapId = existingGapId ?? created;

  if (gapId) {
    return (
      <Link href={`/learning/${gapId}`} className={buttonClass({ variant: "outline", size: "sm" })}>
        In your learning plan →
      </Link>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-2">
      {skillOptions.length > 1 && (
        <NativeSelect aria-label="Skill to learn" value={skill} onChange={(e) => setSkill(e.target.value)} className="w-auto">
          {skillOptions.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </NativeSelect>
      )}
      <Button size="sm" variant="outline" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
        Add to learning plan
      </Button>
      {mutation.isError && (
        <span role="alert" className="text-sm text-destructive">
          {mutation.error instanceof ApiError ? mutation.error.message : "It couldn't be added."}
        </span>
      )}
    </div>
  );
}
