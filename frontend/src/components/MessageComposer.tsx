import { useEffect, useRef, useState } from "react";

import { SendIcon } from "./Icons";

interface MessageComposerProps {
  disabled: boolean;
  errorMessage: string | null;
  onSend: (content: string, image?: File) => Promise<void>;
}

export function MessageComposer({
  disabled,
  errorMessage,
  onSend,
}: MessageComposerProps) {
  const [content, setContent] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!image) { setPreview(null); return; }
    const url = URL.createObjectURL(image);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [image]);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`;
  }, [content]);

  async function submit() {
    const trimmed = content.trim();
    if ((!trimmed && !image) || disabled) return;
    try {
      await onSend(trimmed || 'Explain the text in this image.', image ?? undefined);
      setContent(''); setImage(null); setFileError(null);
    } catch { /* Keep the selected image and question available for retry. */ }
    textareaRef.current?.focus({ preventScroll: true });
  }

  return (
    <div className="mx-auto w-full max-w-3xl shrink-0 px-4 pb-4 sm:px-6 sm:pb-6">
      {(errorMessage || fileError) && (
        <div
          role="alert"
          className="mb-3 rounded-2xl border border-white/[0.08] bg-ink-800 px-4 py-3 text-sm leading-6 text-slate-200 shadow-2xl shadow-black/25"
        >
          {fileError || errorMessage}
        </div>
      )}
      <div className="rounded-2xl border border-white/10 bg-ink-850 p-2 shadow-2xl shadow-black/20 transition focus-within:border-accent-400/30">
        {image && <div className="mb-2 flex items-center gap-3 rounded-xl bg-white/5 p-3">
          {preview && <img src={preview} alt="Selected attachment" className="h-16 w-16 rounded-lg object-contain" />}
          <div className="min-w-0 flex-1"><p className="truncate text-sm text-slate-200">{image.name}</p>
            <p className="text-xs text-slate-400">{disabled ? 'Reading image and preparing your answer…' : 'Ask about the text in this image'}</p></div>
          <button type="button" disabled={disabled} onClick={() => setImage(null)} aria-label="Remove image" className="rounded-lg px-2 py-1 text-slate-300 hover:bg-white/10">×</button>
        </div>}
        <div className="flex items-end gap-2">
          <input ref={fileRef} type="file" accept=".png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff" className="hidden" aria-label="Choose image" onChange={(event) => {
            const file = event.target.files?.[0]; event.target.value = '';
            if (!file) return;
            if (!/\.(png|jpe?g|webp|bmp|tiff?)$/i.test(file.name)) { setFileError('Choose a PNG, JPEG, WebP, BMP or TIFF image.'); return; }
            if (file.size > 25 * 1024 * 1024) { setFileError('Choose an image smaller than 25 MB.'); return; }
            setImage(file); setFileError(null);
          }} />
          <button type="button" aria-label="Attach image" title="Attach image" disabled={disabled} onClick={() => fileRef.current?.click()} className="grid h-11 w-10 shrink-0 place-items-center rounded-xl text-slate-400 hover:bg-white/5 hover:text-white disabled:opacity-50">
            <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1.5"/><path d="m21 15-5-5L5 21"/></svg>
          </button>
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
            disabled={disabled || (!content.trim() && !image)}
            onClick={() => void submit()}
            className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-accent-500 text-ink-950 transition hover:bg-accent-400 disabled:cursor-not-allowed disabled:bg-ink-700 disabled:text-slate-500"
          >
            <SendIcon className="h-4.5 w-4.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
