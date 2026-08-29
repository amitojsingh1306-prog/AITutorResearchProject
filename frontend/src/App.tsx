import { useCallback, useEffect, useState } from "react";

import { chatApi } from "./api/chatApi";
import { AuthPanel } from "./components/AuthPanel";
import { ChatSidebar } from "./components/ChatSidebar";
import { ChatWindow } from "./components/ChatWindow";
import type { ChatDetail, ChatSummary, Message } from "./types/chat";
import type { UserProfile } from "./types/user";

const USER_STORAGE_KEY = "chatbot-tutor-user";
const RATE_LIMIT_MESSAGE = "Your rate limit will reset in 24 hrs.";

function loadStoredUser(): UserProfile | null {
  const stored = window.localStorage.getItem(USER_STORAGE_KEY);
  if (!stored) return null;

  try {
    return JSON.parse(stored) as UserProfile;
  } catch {
    window.localStorage.removeItem(USER_STORAGE_KEY);
    return null;
  }
}

function userFriendlyError(error: unknown, fallback: string): string {
  const message = error instanceof Error ? error.message : fallback;
  return message.toLowerCase().includes("rate limit")
    ? RATE_LIMIT_MESSAGE
    : message;
}

export default function App() {
  const [user, setUser] = useState<UserProfile | null>(() => loadStoredUser());
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [activeChat, setActiveChat] = useState<ChatDetail | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [isLoadingChat, setIsLoadingChat] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isRateLimited = error === RATE_LIMIT_MESSAGE;

  const openChat = useCallback(
    async (chatId: string) => {
      if (!user) return;

      setIsLoadingChat(true);
      setError(null);
      try {
        const chat = await chatApi.get(chatId, user.id);
        setActiveChat(chat);
        setIsSidebarOpen(false);
      } catch (requestError) {
        setError(userFriendlyError(requestError, "Could not restore the conversation."));
      } finally {
        setIsLoadingChat(false);
      }
    },
    [user],
  );

  useEffect(() => {
    async function loadChats() {
      if (!user) {
        setIsLoadingChat(false);
        return;
      }

      setIsLoadingChat(true);
      setActiveChat(null);
      try {
        const previousChats = await chatApi.list(user.id);
        setChats(previousChats);
        if (previousChats.length > 0) {
          await openChat(previousChats[0].id);
        }
      } catch {
        setError("Cannot reach the backend. Start FastAPI on port 8000.");
      } finally {
        setIsLoadingChat(false);
      }
    }
    void loadChats();
  }, [openChat, user]);

  function handleAuth(profile: UserProfile) {
    window.localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(profile));
    setUser(profile);
    setChats([]);
    setActiveChat(null);
    setError(null);
  }

  function handleSignOut() {
    window.localStorage.removeItem(USER_STORAGE_KEY);
    setUser(null);
    setChats([]);
    setActiveChat(null);
    setError(null);
    setIsSidebarOpen(false);
  }

  async function createChat(): Promise<ChatDetail | null> {
    if (!user) return null;

    setIsCreating(true);
    setError(null);
    try {
      const created = await chatApi.create(user.id);
      setChats((current) => [created, ...current]);
      const detail: ChatDetail = { ...created, messages: [] };
      setActiveChat(detail);
      setIsSidebarOpen(false);
      return detail;
    } catch (requestError) {
      setError(userFriendlyError(requestError, "Could not create a conversation."));
      return null;
    } finally {
      setIsCreating(false);
      setIsLoadingChat(false);
    }
  }

  async function sendMessage(content: string) {
    if (isRateLimited) return;

    setIsSending(true);
    setError(null);
    let optimisticMessage: Message | null = null;
    let receivedUserMessage = false;
    let assistantMessageId: string | null = null;
    try {
      const targetChat = activeChat ?? (await createChat());
      if (!targetChat) return;

      if (!user) return;

      optimisticMessage = {
        id: `pending-${crypto.randomUUID()}`,
        chat_id: targetChat.id,
        user_id: user.id,
        role: "user",
        content,
        timestamp: new Date().toISOString(),
        session_id: targetChat.session_id,
      };

      setActiveChat((current) => ({
        ...(current ?? targetChat),
        messages: [
          ...(current?.messages ?? targetChat.messages),
          optimisticMessage as Message,
        ],
      }));

      await chatApi.streamMessage(targetChat.id, content, user.id, {
        onUserMessage: (message) => {
          receivedUserMessage = true;
          setActiveChat((current) => ({
            ...(current ?? targetChat),
            messages: [
              ...(current?.messages ?? targetChat.messages).filter(
                (currentMessage) => currentMessage.id !== optimisticMessage?.id,
              ),
              message,
            ],
          }));
        },
        onAssistantMessageStart: (message) => {
          assistantMessageId = message.id;
          setActiveChat((current) => ({
            ...(current ?? targetChat),
            messages: [...(current?.messages ?? targetChat.messages), message],
          }));
        },
        onChunk: (chunk) => {
          if (!assistantMessageId) return;
          setActiveChat((current) =>
            current
              ? {
                  ...current,
                  messages: current.messages.map((message) =>
                    message.id === assistantMessageId
                      ? { ...message, content: `${message.content}${chunk}` }
                      : message,
                  ),
                }
              : current,
          );
        },
        onDone: ({ assistant_message, chat }) => {
          setActiveChat((current) => ({
            ...(current ?? targetChat),
            ...chat,
            messages: (current?.messages ?? targetChat.messages).map((message) =>
              message.id === assistant_message.id ? assistant_message : message,
            ),
          }));
          setChats((current) => [
            chat,
            ...current.filter((currentChat) => currentChat.id !== chat.id),
          ]);
        },
      });
    } catch (requestError) {
      if (optimisticMessage && !receivedUserMessage) {
        setActiveChat((current) =>
          current
            ? {
                ...current,
                messages: current.messages.filter(
                  (message) => message.id !== optimisticMessage?.id,
                ),
              }
            : current,
        );
      }
      if (assistantMessageId) {
        setActiveChat((current) =>
          current
            ? {
                ...current,
                messages: current.messages.filter(
                  (message) => message.id !== assistantMessageId,
                ),
              }
            : current,
        );
      }
      setError(userFriendlyError(requestError, "The message could not be sent."));
    } finally {
      setIsSending(false);
    }
  }

  if (!user) {
    return <AuthPanel onSubmit={handleAuth} />;
  }

  return (
    <div className="flex h-dvh overflow-hidden bg-ink-900 text-slate-100">
      <ChatSidebar
        chats={chats}
        selectedChatId={activeChat?.id ?? null}
        isOpen={isSidebarOpen}
        isCreating={isCreating}
        onClose={() => setIsSidebarOpen(false)}
        onCreateChat={() => void createChat()}
        onSelectChat={(chatId) => void openChat(chatId)}
      />
      <div className="relative flex min-w-0 flex-1">
        <ChatWindow
          chat={activeChat}
          errorMessage={error}
          isLoadingChat={isLoadingChat}
          isRateLimited={isRateLimited}
          isSending={isSending}
          user={user}
          onSignOut={handleSignOut}
          onOpenSidebar={() => setIsSidebarOpen(true)}
          onSend={sendMessage}
        />
      </div>
    </div>
  );
}
