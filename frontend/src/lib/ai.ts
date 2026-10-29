// Optional AI assistance: whether it's available, and the user's consent.

import { apiFetch } from "@/lib/api";
import type { components } from "@/lib/api-types";
import type { User } from "@/lib/auth";

export type AIStatus = components["schemas"]["AIStatus"];

export const aiKeys = { status: ["ai", "status"] as const };

export const getAIStatus = () => apiFetch<AIStatus>("/ai/status");

export const setAIConsent = (consent: boolean) =>
  apiFetch<User>("/users/me/ai-consent", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ consent }),
  });
