import type {
  ChatDetail,
  ChatMessageResponse,
  ChatSummary,
} from "../types/chat";

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

export const chatApi = {
  list: (userId: string) => request<ChatSummary[]>("/chat/list", userId),

  create: (userId: string) =>
    request<ChatSummary>("/chat/create", userId, {
      method: "POST",
      body: JSON.stringify({}),
    }),

  get: (chatId: string, userId: string) =>
    request<ChatDetail>(`/chat/${chatId}`, userId),

  sendMessage: (chatId: string, content: string, userId: string) =>
    request<ChatMessageResponse>(`/chat/${chatId}/message`, userId, {
      method: "POST",
      body: JSON.stringify({ content }),
    }),
};
