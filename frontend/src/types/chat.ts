export type MessageRole = "user" | "assistant";

export interface ChatSummary {
  id: string;
  title: string;
  user_id: string;
  session_id: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  chat_id: string;
  user_id: string;
  role: MessageRole;
  content: string;
  image_attachment?: { id: string; filename: string; ocr_text: string; truncated?: boolean } | null;
  memory_trace?: {
    memory_action?: {operation:string;status:string};
    embedding_model?: string;
    embedding_dimensions?: number;
    retrieval_latency_ms?: number;
    history_messages_in_prompt?: number;
    prompt_token_upper_bound?: number;
    retrieved_memories?: Array<{
      id: string; document: string; cosine_similarity: number;
      included_in_prompt?: boolean; included_as_history?: boolean;
    }>;
  } | null;
  timestamp: string;
  session_id: string;
}

export interface ChatDetail extends ChatSummary {
  messages: Message[];
}

export interface ChatMessageResponse {
  user_message: Message;
  assistant_message: Message;
  chat: ChatSummary;
}
