import type { ChatSummary } from "../types/chat";
import {
  BookIcon,
  CloseIcon,
  MessageIcon,
  PlusIcon,
  SparkIcon,
} from "./Icons";

const benchmarkLabels = ["LoCoMo", "LongMemEval", "RAGBench", "MT-Bench", "MMLU"];
const memoryLabels = ["Buffer", "Rolling summary", "Vector summary", "Graph memory"];

interface ChatSidebarProps {
  chats: ChatSummary[];
  selectedChatId: string | null;
  isOpen: boolean;
  isCreating: boolean;
  onClose: () => void;
  onCreateChat: () => void;
  onSelectChat: (chatId: string) => void;
}

function relativeDate(value: string): string {
  const date = new Date(value);
  const today = new Date();
  const isToday = date.toDateString() === today.toDateString();
  return isToday
    ? date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : date.toLocaleDateString([], { month: "short", day: "numeric" });
}

export function ChatSidebar({
  chats,
  selectedChatId,
  isOpen,
  isCreating,
  onClose,
  onCreateChat,
  onSelectChat,
}: ChatSidebarProps) {
  return (
    <>
      {isOpen && (
        <button
          type="button"
          aria-label="Close sidebar"
          className="fixed inset-0 z-30 bg-black/60 backdrop-blur-sm md:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-[290px] flex-col border-r border-white/[0.07] bg-ink-950 transition-transform duration-300 md:static md:translate-x-0 ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-20 items-center justify-between px-5">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl border border-accent-400/20 bg-accent-500/10 text-accent-400 shadow-glow">
              <BookIcon className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold tracking-wide text-white">
                ChatbotTutor
                <span className="text-accent-400">AI</span>
              </p>
              <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
                Local research tutor
              </p>
            </div>
          </div>
          <button
            type="button"
            aria-label="Close sidebar"
            className="rounded-lg p-2 text-slate-400 hover:bg-white/5 hover:text-white md:hidden"
            onClick={onClose}
          >
            <CloseIcon className="h-5 w-5" />
          </button>
        </div>

        <div className="px-4 pb-5">
          <button
            type="button"
            onClick={onCreateChat}
            disabled={isCreating}
            className="group flex w-full items-center justify-center gap-2 rounded-xl border border-accent-400/30 bg-accent-500/10 px-4 py-3 text-sm font-medium text-accent-400 transition hover:border-accent-400/50 hover:bg-accent-500/15 disabled:cursor-wait disabled:opacity-60"
          >
            <PlusIcon className="h-4 w-4 transition-transform group-hover:rotate-90" />
            {isCreating ? "Creating…" : "New chat"}
          </button>
        </div>

        <div className="flex items-center gap-2 px-5 pb-3 text-[11px] font-medium uppercase tracking-[0.18em] text-slate-600">
          <MessageIcon className="h-3.5 w-3.5" />
          Previous chats
        </div>

        <nav className="min-h-0 flex-1 space-y-1 overflow-y-auto px-3 pb-5">
          {chats.length === 0 ? (
            <div className="mx-2 rounded-xl border border-dashed border-white/10 px-4 py-6 text-center">
              <SparkIcon className="mx-auto mb-2 h-5 w-5 text-slate-600" />
              <p className="text-xs leading-5 text-slate-500">
                Your conversations will appear here.
              </p>
            </div>
          ) : (
            chats.map((chat) => {
              const isSelected = chat.id === selectedChatId;
              return (
                <button
                  type="button"
                  key={chat.id}
                  onClick={() => onSelectChat(chat.id)}
                  className={`group flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left transition ${
                    isSelected
                      ? "bg-white/[0.07] text-white"
                      : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-200"
                  }`}
                >
                  <span
                    className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                      isSelected ? "bg-accent-400" : "bg-slate-700"
                    }`}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm">{chat.title}</span>
                    <span className="mt-0.5 block text-[11px] text-slate-600">
                      {relativeDate(chat.updated_at)}
                    </span>
                  </span>
                </button>
              );
            })
          )}
        </nav>

        <div className="border-t border-white/[0.06] px-5 py-4">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-slate-600">
            Evaluation track
          </p>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {benchmarkLabels.map((label) => (
              <span
                key={label}
                className="rounded-md border border-white/[0.07] bg-white/[0.03] px-2 py-1 text-[11px] font-medium text-slate-400"
              >
                {label}
              </span>
            ))}
          </div>
          <p className="mt-4 text-[11px] font-medium uppercase tracking-[0.18em] text-slate-600">
            Memory layers
          </p>
          <div className="mt-3 grid grid-cols-2 gap-1.5">
            {memoryLabels.map((label) => (
              <span
                key={label}
                className="rounded-md bg-accent-500/10 px-2 py-1 text-[11px] text-accent-300"
              >
                {label}
              </span>
            ))}
          </div>
        </div>

        <div className="border-t border-white/[0.06] px-5 py-4">
          <div className="flex items-center gap-2 text-xs text-slate-600">
            <span className="h-2 w-2 rounded-full bg-accent-500 shadow-[0_0_8px_rgba(66,207,168,0.7)]" />
            Local-first foundation · Phase 1
          </div>
        </div>
      </aside>
    </>
  );
}
