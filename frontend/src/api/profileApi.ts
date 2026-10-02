import type { LearnerProfile, OnboardingAnswers } from "../types/profile";

const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

async function request<T>(
  path: string,
  userId: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-User-Id": userId,
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      detail?: string;
    } | null;
    throw new Error(body?.detail ?? `Request failed with status ${response.status}.`);
  }

  return response.json() as Promise<T>;
}

interface LoginResponse {
  profile: LearnerProfile;
  onboarding_complete: boolean;
  confirmation_email_sent: boolean;
}

interface OnboardingResponse {
  profile: LearnerProfile;
}

export const profileApi = {
  login: (userId: string, name: string, email: string) =>
    request<LoginResponse>("/auth/login", userId, {
      method: "POST",
      body: JSON.stringify({ name, email }),
    }),

  get: (userId: string) => request<LearnerProfile>("/profile", userId),

  completeOnboarding: (userId: string, answers: OnboardingAnswers) =>
    request<OnboardingResponse>("/profile/onboarding", userId, {
      method: "POST",
      body: JSON.stringify(answers),
    }),
};
