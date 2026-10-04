const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

export interface MemoryDebugItem {
  id: string;
  document: string;
  metadata: Record<string, string | number | boolean | null>;
  embedding_length: number;
  embedding_preview: number[];
}

export interface MemoryDebugResponse {
  collection: string;
  count: number;
  items: MemoryDebugItem[];
}

export const memoryApi = {
  async debug(limit = 10): Promise<MemoryDebugResponse> {
    const response = await fetch(`${API_URL}/memory/debug?limit=${limit}`);
    if (!response.ok) {
      throw new Error(`Memory debug request failed with status ${response.status}.`);
    }
    return response.json() as Promise<MemoryDebugResponse>;
  },
};
