// Typed client for requirement analyses.

import { ApiError, apiFetch } from "@/lib/api";
import type { components } from "@/lib/api-types";

type Schemas = components["schemas"];

export type Analysis = Schemas["AnalysisRead"];
export type Requirement = Schemas["RequirementRead"];
export type Evidence = Schemas["EvidenceRead"];
export type EvidenceStatus = Schemas["EvidenceStatus"];
export type Importance = Schemas["Importance"];
export type Category = Schemas["Category"];
export type SelfReport = Schemas["SelfReport"];
export type Relevance = Schemas["Relevance"];
export type RequirementUpdate = Schemas["RequirementUpdate"];

// Nested under "applications" on purpose: any change to an application (new job
// description, different CV) invalidates its analysis too, so "out of date" shows at once.
export const analysisKeys = {
  latest: (applicationId: string) => ["applications", "analysis", applicationId] as const,
};

/** The latest analysis, or null if the application hasn't been analysed yet. */
export async function getLatestAnalysis(applicationId: string): Promise<Analysis | null> {
  try {
    return await apiFetch<Analysis>(`/applications/${applicationId}/analyses/latest`);
  } catch (error) {
    if (error instanceof ApiError && error.code === "no_analysis") return null;
    throw error;
  }
}

export const runAnalysis = (applicationId: string) =>
  apiFetch<Analysis>(`/applications/${applicationId}/analyses`, { method: "POST" });

export const updateRequirement = (id: string, body: RequirementUpdate) =>
  apiFetch<Requirement>(`/requirements/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
