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
