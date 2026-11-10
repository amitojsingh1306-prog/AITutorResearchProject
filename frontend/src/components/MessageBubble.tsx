import type { Message } from "../types/chat";
import { useEffect, useState } from 'react';
import { chatApi } from '../api/chatApi';
import { SparkIcon } from "./Icons";
import { MarkdownContent } from "./MarkdownContent";

interface MessageBubbleProps {
  message: Message;
}

function ImageAttachment({ message }: { message: Message }) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const attachment = message.image_attachment!;
  useEffect(() => {
    let active = true;
    let objectUrl: string | null = null;
    void chatApi.imageBlob(message.chat_id, attachment.id, message.user_id).then((blob) => {
      if (!active) return;
      objectUrl = URL.createObjectURL(blob); setUrl(objectUrl);
    }).catch(() => { if (active) setFailed(true); });
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [message.chat_id, message.user_id, attachment.id]);
  return <div className="mb-3">
    {url && <a href={url} target="_blank" rel="noreferrer"><img src={url} alt={attachment.filename} className="max-h-64 max-w-full rounded-xl object-contain" /></a>}
    <p className="text-xs opacity-80">{attachment.filename}{failed ? ' · Image unavailable or expired' : ''}</p>
    <details className="mt-1 text-xs opacity-80"><summary className="cursor-pointer">Extracted text</summary><p className="mt-2 whitespace-pre-wrap">{attachment.ocr_text}{attachment.truncated ? '\n[Excerpt]' : ''}</p></details>
  </div>;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex gap-4 ${isUser ? "justify-end" : "w-full justify-start"}`}>
      {!isUser && (
        <div className="mt-1 grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-accent-400/20 bg-accent-500/10 text-accent-400">
          <SparkIcon className="h-4 w-4" />
        </div>
      )}
      <div
        className={`min-w-0 text-[15px] leading-7 ${
          isUser
            ? "max-w-[82%] rounded-2xl rounded-br-md bg-accent-600 px-4 py-3 text-white sm:max-w-[64%]"
            : "flex-1 py-2 text-slate-200"
        }`}
      >
        {message.image_attachment && <ImageAttachment message={message} />}
        {isUser ? (
          <p className="whitespace-pre-wrap break-words">{message.content}</p>
        ) : (
          <MarkdownContent content={message.content} />
        )}
        <p
          className={`mt-1.5 text-[10px] ${
            isUser ? "text-emerald-100/60" : "text-slate-600"
          }`}
        >
          {new Date(message.timestamp).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </p>
      </div>
    </div>
  );
}
