import type {
  ChatDetail,
  ChatMessageResponse,
  ChatSummary,
  Message,
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

interface StreamDonePayload {
  assistant_message: Message;
  chat: ChatSummary;
}

interface StreamHandlers {
  onUserMessage: (message: Message) => void;
  onAssistantMessageStart: (message: Message) => void;
  onChunk: (content: string) => void;
  onDone: (payload: StreamDonePayload) => void;
}

function findSseSeparator(buffer: string): { index: number; length: number } | null {
  const newlineIndex = buffer.indexOf("\n\n");
  const crlfIndex = buffer.indexOf("\r\n\r\n");

  if (newlineIndex === -1 && crlfIndex === -1) return null;
  if (newlineIndex === -1) return { index: crlfIndex, length: 4 };
  if (crlfIndex === -1) return { index: newlineIndex, length: 2 };

  return newlineIndex < crlfIndex
    ? { index: newlineIndex, length: 2 }
    : { index: crlfIndex, length: 4 };
}

function parseSseEvent(block: string): { event: string; data: unknown } | null {
  const lines = block.split(/\r?\n/);
  const eventLine = lines.find((line) => line.startsWith("event:"));
  const dataLines = lines
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice("data:".length).trimStart());

  if (!eventLine || dataLines.length === 0) return null;

  return {
    event: eventLine.slice("event:".length).trim(),
    data: JSON.parse(dataLines.join("\n")) as unknown,
  };
}

async function streamRequest(
  path: string,
  userId: string,
  body: object,
  handlers: StreamHandlers,
): Promise<void> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-User-Id": userId,
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const responseBody = (await response.json().catch(() => null)) as {
      detail?: string;
    } | null;
    throw new Error(
      responseBody?.detail ?? `Request failed with status ${response.status}.`,
    );
  }

  if (!response.body) {
    throw new Error("Streaming response is not available in this browser.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });

    let separator = findSseSeparator(buffer);
    while (separator) {
      const block = buffer.slice(0, separator.index);
      buffer = buffer.slice(separator.index + separator.length);
      const parsed = parseSseEvent(block);

      if (parsed?.event === "user_message") {
        handlers.onUserMessage(parsed.data as Message);
      } else if (parsed?.event === "assistant_message_start") {
        handlers.onAssistantMessageStart(parsed.data as Message);
      } else if (parsed?.event === "chunk") {
        handlers.onChunk((parsed.data as { content: string }).content);
      } else if (parsed?.event === "done") {
        handlers.onDone(parsed.data as StreamDonePayload);
        await reader.cancel().catch(() => undefined);
        return;
      } else if (parsed?.event === "error") {
        throw new Error((parsed.data as { detail?: string }).detail ?? "Stream failed.");
      }

      separator = findSseSeparator(buffer);
    }

    if (done) break;
  }

  const parsed = buffer.trim() ? parseSseEvent(buffer) : null;
  if (parsed?.event === "done") {
    handlers.onDone(parsed.data as StreamDonePayload);
  } else if (parsed?.event === "error") {
    throw new Error((parsed.data as { detail?: string }).detail ?? "Stream failed.");
  }
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

  streamMessage: (
    chatId: string,
    content: string,
    userId: string,
    handlers: StreamHandlers,
  ) => streamRequest(`/chat/${chatId}/message/stream`, userId, { content }, handlers),
};
