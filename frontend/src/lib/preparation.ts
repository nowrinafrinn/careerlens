// Typed client for position-specific preparation.

import { apiFetch } from "@/lib/api";
import type { components } from "@/lib/api-types";
import { type Task } from "@/lib/learning";

type Schemas = components["schemas"];

export type Preparation = Schemas["PreparationRead"];
export type Suggestion = Schemas["SuggestionRead"];
export type SuggestionKind = Schemas["SuggestionKind"];

// Under "applications" so changes to the application, its analysis or rounds refresh these too.
export const preparationKeys = {
  suggestions: (applicationId: string, roundId: string | null) =>
    ["applications", "preparation", applicationId, roundId ?? "all"] as const,
  checklist: (applicationId: string, roundId: string | null) =>
    ["applications", "prep-tasks", applicationId, roundId ?? "all"] as const,
};

export function getPreparation(applicationId: string, roundId: string | null): Promise<Preparation> {
  const query = roundId ? `?${new URLSearchParams({ round_id: roundId })}` : "";
  return apiFetch<Preparation>(`/applications/${applicationId}/preparation${query}`);
}

export function listPrepTasks(applicationId: string, roundId: string | null): Promise<Task[]> {
  const params = new URLSearchParams({ kind: "preparation" });
  if (roundId) params.set("recruitment_round_id", roundId);
  else params.set("application_id", applicationId);
  return apiFetch<Task[]>(`/tasks?${params}`);
}
