import { useEffect, useRef } from "react";

import type { ChatDetail } from "../types/chat";
import type { UserProfile } from "../types/user";
import { BookIcon, MenuIcon, SparkIcon } from "./Icons";
import { LoadingBubble } from "./LoadingBubble";
import { MessageBubble } from "./MessageBubble";
import { MessageComposer } from "./MessageComposer";

const benchmarks = [
  ["Long-term memory", "LoCoMo"],
  ["Memory retention", "LongMemEval"],
  ["Retrieval performance", "RAGBench"],
  ["General chatbot ability", "MT-Bench"],
  ["Educational knowledge", "MMLU"],
] as const;

const memoryPlan = [
  ["Buffer", "Raw recent chat"],
  ["Rolling summary", "Old chat memory"],
  ["Vector summary", "Semantic search of past chats"],
  ["Graph memory", "Structured learner knowledge"],
] as const;

interface ChatWindowProps {
  chat: ChatDetail | null;
  errorMessage: string | null;
  isLoadingChat: boolean;
  isRateLimited: boolean;
  isSending: boolean;
  user: UserProfile;
  onSignOut: () => void;
  onOpenSidebar: () => void;
  onSend: (content: string) => Promise<void>;
}

export function ChatWindow({
  chat,
  errorMessage,
  isLoadingChat,
  isRateLimited,
  isSending,
  user,
  onSignOut,
  onOpenSidebar,
  onSend,
}: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat?.messages, isSending]);

  return (
    <main className="flex min-w-0 flex-1 flex-col bg-ink-900">
      <header className="flex h-16 shrink-0 items-center gap-3 border-b border-white/[0.06] px-4 sm:px-6">
        <button
          type="button"
          aria-label="Open sidebar"
          className="rounded-lg p-2 text-slate-400 hover:bg-white/5 hover:text-white md:hidden"
          onClick={onOpenSidebar}
        >
          <MenuIcon className="h-5 w-5" />
        </button>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-slate-200">
            {chat?.title ?? "New learning session"}
          </p>
          <p className="text-[11px] text-slate-600">
            Hybrid Memory Tutor · Local workspace
          </p>
        </div>
        <div className="hidden min-w-0 items-center gap-3 sm:flex">
          <div className="min-w-0 rounded-full border border-white/[0.07] bg-white/[0.03] px-3 py-1.5 text-[11px] text-slate-500">
            <span className="mr-2 inline-block h-1.5 w-1.5 rounded-full bg-accent-400" />
            <span className="text-slate-300">{user.name}</span>
          </div>
          <button
            type="button"
            className="rounded-lg border border-white/[0.07] px-3 py-1.5 text-xs text-slate-500 transition hover:border-white/[0.14] hover:text-slate-200"
            onClick={onSignOut}
          >
            Sign out
          </button>
        </div>
      </header>

      <section className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex min-h-full w-full max-w-6xl flex-col px-4 py-8 sm:px-8 lg:px-10">
          {isLoadingChat ? (
            <div className="grid flex-1 place-items-center">
              <div className="flex items-center gap-3 text-sm text-slate-500">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-700 border-t-accent-400" />
                Restoring conversation…
              </div>
            </div>
          ) : !chat || chat.messages.length === 0 ? (
            <div className="grid flex-1 place-items-center py-6">
              <div className="w-full max-w-2xl">
                <div className="relative mx-auto mb-6 grid h-16 w-16 place-items-center rounded-2xl border border-accent-400/20 bg-accent-500/10 text-accent-400 shadow-glow">
                  <BookIcon className="h-7 w-7" />
                  <SparkIcon className="absolute -right-2 -top-2 h-5 w-5 text-accent-400" />
                </div>
                <div className="text-center">
                  <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">
                    What would you like to learn?
                  </h1>
                  <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-slate-500">
                    Start a conversation with your AI tutor. The research track
                    below keeps the hybrid-memory goal and benchmark coverage visible.
                  </p>
                </div>

                <div className="mt-8 grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
                  <section className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-4">
                    <h2 className="text-sm font-semibold text-slate-200">
                      Benchmark Coverage
                    </h2>
                    <div className="mt-4 divide-y divide-white/[0.06]">
                      {benchmarks.map(([aspect, benchmark]) => (
                        <div
                          key={benchmark}
                          className="grid grid-cols-[1fr_auto] gap-4 py-3 first:pt-0 last:pb-0"
                        >
                          <span className="text-sm text-slate-400">{aspect}</span>
                          <span className="text-sm font-semibold text-white">
                            {benchmark}
                          </span>
                        </div>
                      ))}
                    </div>
                  </section>

                  <section className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-4">
                    <h2 className="text-sm font-semibold text-slate-200">
                      Hybrid Memory Plan
                    </h2>
                    <div className="mt-4 space-y-3">
                      {memoryPlan.map(([layer, purpose]) => (
                        <div key={layer}>
                          <div className="flex items-center gap-2">
                            <span className="h-1.5 w-1.5 rounded-full bg-accent-400" />
                            <span className="text-sm font-medium text-white">
                              {layer}
                            </span>
                          </div>
                          <p className="mt-1 pl-3.5 text-xs leading-5 text-slate-500">
                            {purpose}
                          </p>
                        </div>
                      ))}
                    </div>
                  </section>
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-6 py-2">
              {chat.messages.map((message) => (
                <MessageBubble key={message.id} message={message} />
              ))}
              {isSending && <LoadingBubble />}
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </section>

      <MessageComposer
        disabled={isSending || isRateLimited}
        errorMessage={errorMessage}
        onSend={onSend}
      />
    </main>
  );
}
