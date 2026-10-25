// Typed client for CV recommendations.

import { apiFetch } from "@/lib/api";
import type { components } from "@/lib/api-types";

type Schemas = components["schemas"];

export type Recommendation = Schemas["RecommendationRead"];
export type RecommendationKind = Schemas["Kind"];
export type ChangeType = Schemas["ChangeType"];
export type Decision = Schemas["RecommendationDecision"];

// Under "applications" so that any change to the application or its analysis refreshes these too.
export const recommendationKeys = {
  forAnalysis: (analysisId: string) => ["applications", "recommendations", analysisId] as const,
};

export const listRecommendations = (analysisId: string) =>
  apiFetch<Recommendation[]>(`/analyses/${analysisId}/recommendations`);

export const decideRecommendation = (id: string, body: Decision) =>
  apiFetch<Recommendation>(`/recommendations/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
