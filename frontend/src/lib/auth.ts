import { apiFetch } from "@/lib/api";

// Mirrors backend/app/schemas/auth.py UserRead
export type User = {
  id: string;
  email: string;
  display_name: string | null;
  ai_processing_consent_at: string | null;
  created_at: string;
};

export type Credentials = { email: string; password: string };

const jsonPost = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const getCurrentUser = () => apiFetch<User>("/auth/me");

export const login = (credentials: Credentials) => apiFetch<User>("/auth/login", jsonPost(credentials));

export const register = (data: Credentials & { display_name?: string }) =>
  apiFetch<User>("/auth/register", jsonPost(data));

export const logout = () => apiFetch<null>("/auth/logout", { method: "POST" });

/** Only follow same-site paths after login, so a crafted ?next= link can't send users elsewhere. */
export function safeNextPath(raw: string | null): string {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//") || raw.startsWith("/\\")) return "/";
  return raw;
}
