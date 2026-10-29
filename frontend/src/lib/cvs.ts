// Typed client for /api/v1/cv-versions.

import { apiFetch } from "@/lib/api";
import type { components } from "@/lib/api-types";

type Schemas = components["schemas"];

export type CVSummary = Schemas["CVVersionSummary"];
export type CVDetail = Schemas["CVVersionDetail"];
export type CVSection = Schemas["SectionRead"];
export type SectionType = Schemas["SectionType"];
export type ParseStatus = Schemas["ParseStatus"];

// Keep in step with CV_MAX_BYTES on the backend. 4 MB fits Vercel's 4.5 MB request limit.
export const MAX_CV_BYTES = 4 * 1024 * 1024;
export const MAX_CV_MB = MAX_CV_BYTES / (1024 * 1024);

export const cvKeys = {
  all: ["cvs"] as const,
  list: () => ["cvs", "list"] as const,
  detail: (id: string) => ["cvs", "detail", id] as const,
};

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const listCVs = () => apiFetch<CVSummary[]>("/cv-versions");

export const getCV = (id: string) => apiFetch<CVDetail>(`/cv-versions/${id}`);

export function uploadCV(file: File, label?: string): Promise<CVDetail> {
  const form = new FormData();
  form.append("file", file);
  if (label) form.append("label", label);
  // No Content-Type header: the browser sets multipart/form-data with its boundary.
  return apiFetch<CVDetail>("/cv-versions", { method: "POST", body: form });
}

export const updateCV = (id: string, body: { label?: string; is_confirmed?: boolean }) =>
  apiFetch<CVDetail>(`/cv-versions/${id}`, json("PATCH", body));

export const updateSection = (cvId: string, sectionId: string, sectionType: SectionType) =>
  apiFetch<CVSection>(`/cv-versions/${cvId}/sections/${sectionId}`, json("PATCH", { section_type: sectionType }));

export const deleteCV = (id: string) => apiFetch<null>(`/cv-versions/${id}`, { method: "DELETE" });

export const originalFileUrl = (id: string) => `/api/v1/cv-versions/${id}/file`;

export function formatFileSize(bytes: number): string {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
