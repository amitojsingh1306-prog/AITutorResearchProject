import { useEffect, useRef, useState } from "react";

import { SendIcon } from "./Icons";

interface MessageComposerProps {
  disabled: boolean;
  errorMessage: string | null;
  onSend: (content: string) => Promise<void>;
}

export function MessageComposer({
  disabled,
  errorMessage,
  onSend,
}: MessageComposerProps) {
  const [content, setContent] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`;
  }, [content]);

  async function submit() {
    const trimmed = content.trim();
    if (!trimmed || disabled) return;
    setContent("");
    await onSend(trimmed);
    textareaRef.current?.focus();
  }

  return (
    <div className="mx-auto w-full max-w-3xl px-4 pb-4 sm:px-6 sm:pb-6">
      {errorMessage && (
        <div
          role="alert"
          className="mb-3 rounded-2xl border border-white/[0.08] bg-ink-800 px-4 py-3 text-sm leading-6 text-slate-200 shadow-2xl shadow-black/25"
        >
          {errorMessage}
        </div>
      )}
      <div className="rounded-2xl border border-white/10 bg-ink-850 p-2 shadow-2xl shadow-black/20 transition focus-within:border-accent-400/30">
        <div className="flex items-end gap-2">
          <textarea
            ref={textareaRef}
            rows={1}
            value={content}
            disabled={disabled}
            placeholder={
              disabled && errorMessage
                ? "Messaging is paused…"
                : "Ask your tutor anything…"
            }
            aria-label="Message"
            onChange={(event) => setContent(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void submit();
              }
            }}
            className="min-h-11 flex-1 resize-none bg-transparent px-3 py-2.5 text-[15px] leading-6 text-slate-100 outline-none placeholder:text-slate-600 disabled:cursor-not-allowed"
          />
          <button
            type="button"
            aria-label="Send message"
            disabled={disabled || !content.trim()}
            onClick={() => void submit()}
            className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-accent-500 text-ink-950 transition hover:bg-accent-400 disabled:cursor-not-allowed disabled:bg-ink-700 disabled:text-slate-500"
          >
            <SendIcon className="h-4.5 w-4.5" />
          </button>
        </div>
      </div>
      <p className="mt-2 text-center text-[10px] text-slate-600">
        Phase 1 uses a placeholder response. Ollama is intentionally not connected.
      </p>
    </div>
  );
}
