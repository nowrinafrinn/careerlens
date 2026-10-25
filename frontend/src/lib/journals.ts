// Typed client for journals and the question bank.

import { apiFetch } from "@/lib/api";
import type { components } from "@/lib/api-types";

type Schemas = components["schemas"];

export type JournalTemplate = Schemas["JournalTemplate"];
export type TemplateInfo = Schemas["TemplateRead"];
export type Journal = Schemas["JournalRead"];
export type JournalCreate = Schemas["JournalCreate"];
export type JournalUpdate = Schemas["JournalUpdate"];
export type QuestionFields = Schemas["QuestionFields"];
export type Question = Schemas["QuestionRead"];
export type QuestionDetail = Schemas["QuestionDetail"];
export type QuestionPage = Schemas["Page_QuestionRead_"];
export type QuestionUpdate = Schemas["QuestionUpdate"];
export type QuestionCreate = Schemas["QuestionCreate"];
export type AttemptCreate = Schemas["AttemptCreate"];
export type Facets = Schemas["QuestionFacets"];
export type Difficulty = Schemas["Difficulty"];
export type ResponseQuality = Schemas["ResponseQuality"];
export type PracticeStatus = Schemas["PracticeStatus"];

// Journals sit under "applications" so the application page (journals list, history) refreshes too.
export const journalKeys = {
  templates: ["journal-templates"] as const,
  forApplication: (applicationId: string) => ["applications", "journals", applicationId] as const,
  detail: (id: string) => ["applications", "journal", id] as const,
};

export const questionKeys = {
  all: ["questions"] as const,
  search: (params: Record<string, string>) => ["questions", "search", params] as const,
  facets: ["questions", "facets"] as const,
  detail: (id: string) => ["questions", "detail", id] as const,
};

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const getTemplates = () => apiFetch<TemplateInfo[]>("/journal-templates");
export const listJournals = (applicationId: string) =>
  apiFetch<Journal[]>(`/journals?${new URLSearchParams({ application_id: applicationId })}`);
export const getJournal = (id: string) => apiFetch<Journal>(`/journals/${id}`);
export const createJournal = (body: JournalCreate) => apiFetch<Journal>("/journals", json("POST", body));
export const updateJournal = (id: string, body: JournalUpdate) => apiFetch<Journal>(`/journals/${id}`, json("PATCH", body));
export const addJournalQuestions = (id: string, body: QuestionFields[]) =>
  apiFetch<Journal>(`/journals/${id}/questions`, json("POST", body));
export const deleteJournal = (id: string) => apiFetch<null>(`/journals/${id}`, { method: "DELETE" });

export const searchQuestions = (params: Record<string, string>) =>
  apiFetch<QuestionPage>(`/questions?${new URLSearchParams(params)}`);
export const getFacets = () => apiFetch<Facets>("/questions/facets");
export const getQuestion = (id: string) => apiFetch<QuestionDetail>(`/questions/${id}`);
export const createQuestion = (body: QuestionCreate) => apiFetch<QuestionDetail>("/questions", json("POST", body));
export const updateQuestion = (id: string, body: QuestionUpdate) =>
  apiFetch<QuestionDetail>(`/questions/${id}`, json("PATCH", body));
export const addAttempt = (id: string, body: AttemptCreate) =>
  apiFetch<QuestionDetail>(`/questions/${id}/attempts`, json("POST", body));
