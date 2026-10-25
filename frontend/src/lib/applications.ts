// Typed client for /api/v1/applications and /api/v1/rounds.
// Types come from src/lib/api-types.ts, generated from the backend's OpenAPI
// schema (`npm run gen:api`), so they can't silently drift from the API.

import { apiFetch } from "@/lib/api";
import type { components } from "@/lib/api-types";

type Schemas = components["schemas"];

export type ApplicationStatus = Schemas["ApplicationStatus"];
export type Application = Schemas["ApplicationRead"];
export type ApplicationDetail = Schemas["ApplicationDetail"];
export type ApplicationCreate = Schemas["ApplicationCreate"];
export type ApplicationUpdate = Schemas["ApplicationUpdate"];
export type ApplicationPage = Schemas["Page_ApplicationRead_"];
export type Round = Schemas["RoundRead"];
export type RoundCreate = Schemas["RoundCreate"];
export type RoundUpdate = Schemas["RoundUpdate"];
export type RoundType = Schemas["RoundType"];
export type RoundStatus = Schemas["RoundStatus"];
export type RoundResult = Schemas["RoundResult"];
export type RecruitmentEvent = Schemas["EventRead"];

export type ListParams = {
  status?: ApplicationStatus;
  q?: string;
  includeArchived?: boolean;
  limit?: number;
  offset?: number;
};

// Every key starts with "applications", so one invalidation refreshes lists,
// details and timelines after any change.
export const applicationKeys = {
  all: ["applications"] as const,
  list: (params: ListParams) => ["applications", "list", params] as const,
  detail: (id: string) => ["applications", "detail", id] as const,
  timeline: (id: string) => ["applications", "timeline", id] as const,
};

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export function listApplications(params: ListParams): Promise<ApplicationPage> {
  const search = new URLSearchParams();
  if (params.status) search.set("status", params.status);
  if (params.q) search.set("q", params.q);
  if (params.includeArchived) search.set("include_archived", "true");
  if (params.limit) search.set("limit", String(params.limit));
  if (params.offset) search.set("offset", String(params.offset));
  const query = search.toString();
  return apiFetch<ApplicationPage>(`/applications${query ? `?${query}` : ""}`);
}

export const getApplication = (id: string) => apiFetch<ApplicationDetail>(`/applications/${id}`);

export const createApplication = (body: ApplicationCreate) =>
  apiFetch<ApplicationDetail>("/applications", json("POST", body));

export const updateApplication = (id: string, body: ApplicationUpdate) =>
  apiFetch<ApplicationDetail>(`/applications/${id}`, json("PATCH", body));

export const setArchived = (id: string, archived: boolean) =>
  apiFetch<ApplicationDetail>(`/applications/${id}/${archived ? "archive" : "restore"}`, { method: "POST" });

export const getTimeline = (id: string) => apiFetch<RecruitmentEvent[]>(`/applications/${id}/timeline`);

export const createRound = (applicationId: string, body: RoundCreate) =>
  apiFetch<Round>(`/applications/${applicationId}/rounds`, json("POST", body));

export const updateRound = (id: string, body: RoundUpdate) => apiFetch<Round>(`/rounds/${id}`, json("PATCH", body));

export function deleteRound(id: string, reason?: string): Promise<null> {
  const query = reason ? `?${new URLSearchParams({ reason })}` : "";
  return apiFetch<null>(`/rounds/${id}${query}`, { method: "DELETE" });
}
