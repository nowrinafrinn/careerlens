// Typed client for skill gaps, learning tasks and reassessments.

import { apiFetch } from "@/lib/api";
import type { components } from "@/lib/api-types";

type Schemas = components["schemas"];

export type GapSummary = Schemas["GapSummary"];
export type GapDetail = Schemas["GapDetail"];
export type GapType = Schemas["GapType"];
export type GapStatus = Schemas["GapStatus"];
export type Level = Schemas["Level"];
export type EvidenceBasis = Schemas["EvidenceBasis"];
export type GapCreate = Schemas["GapCreate"];
export type GapUpdate = Schemas["GapUpdate"];
export type ReassessmentCreate = Schemas["ReassessmentCreate"];
export type Task = Schemas["TaskRead"];
export type TaskCreate = Schemas["TaskCreate"];
export type TaskUpdate = Schemas["TaskUpdate"];
export type TaskStatus = Schemas["TaskStatus"];
export type AttemptOutcome = Schemas["AttemptOutcome"];
export type TaskAttemptCreate = Schemas["TaskAttemptCreate"];

export const learningKeys = {
  all: ["learning"] as const,
  gaps: ["learning", "gaps"] as const,
  gap: (id: string) => ["learning", "gap", id] as const,
};

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const listGaps = () => apiFetch<GapSummary[]>("/skill-gaps");
export const getGap = (id: string) => apiFetch<GapDetail>(`/skill-gaps/${id}`);
export const createGap = (body: GapCreate) => apiFetch<GapDetail>("/skill-gaps", json("POST", body));
export const updateGap = (id: string, body: GapUpdate) => apiFetch<GapDetail>(`/skill-gaps/${id}`, json("PATCH", body));
export const reassessGap = (id: string, body: ReassessmentCreate) =>
  apiFetch<GapDetail>(`/skill-gaps/${id}/reassessments`, json("POST", body));
export const gapFromRequirement = (requirementId: string, skillName?: string) =>
  apiFetch<GapDetail>(`/requirements/${requirementId}/skill-gap`, json("POST", skillName ? { skill_name: skillName } : {}));
export const gapFromQuestion = (questionId: string, skillName?: string) =>
  apiFetch<GapDetail>(`/questions/${questionId}/skill-gap`, json("POST", skillName ? { skill_name: skillName } : {}));

export const createTask = (body: TaskCreate) => apiFetch<Task>("/tasks", json("POST", body));
export const updateTask = (id: string, body: TaskUpdate) => apiFetch<Task>(`/tasks/${id}`, json("PATCH", body));
export const deleteTask = (id: string) => apiFetch<null>(`/tasks/${id}`, { method: "DELETE" });
export const addTaskAttempt = (id: string, body: TaskAttemptCreate) =>
  apiFetch<Task>(`/tasks/${id}/attempts`, json("POST", body));
