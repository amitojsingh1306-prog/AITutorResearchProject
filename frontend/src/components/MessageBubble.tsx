import type { Message } from "../types/chat";
import { SparkIcon } from "./Icons";
import { MarkdownContent } from "./MarkdownContent";

interface MessageBubbleProps {
  message: Message;
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
