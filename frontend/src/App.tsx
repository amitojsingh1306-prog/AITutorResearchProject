import { useCallback, useEffect, useState } from "react";

import { chatApi } from "./api/chatApi";
import { AuthPanel } from "./components/AuthPanel";
import { ChatSidebar } from "./components/ChatSidebar";
import { ChatWindow } from "./components/ChatWindow";
import type { ChatDetail, ChatSummary } from "./types/chat";
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
    try {
      const targetChat = activeChat ?? (await createChat());
      if (!targetChat) return;

      if (!user) return;

      const response = await chatApi.sendMessage(targetChat.id, content, user.id);
      setActiveChat((current) => ({
        ...(current ?? targetChat),
        ...response.chat,
        messages: [
          ...(current?.messages ?? targetChat.messages),
          response.user_message,
          response.assistant_message,
        ],
      }));
      setChats((current) => [
        response.chat,
        ...current.filter((chat) => chat.id !== response.chat.id),
      ]);
    } catch (requestError) {
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
