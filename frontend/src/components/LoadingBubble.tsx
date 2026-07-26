import { SparkIcon } from "./Icons";

export function LoadingBubble() {
  return (
    <div className="flex items-center gap-3">
      <div className="grid h-8 w-8 place-items-center rounded-lg border border-accent-400/20 bg-accent-500/10 text-accent-400">
        <SparkIcon className="h-4 w-4" />
      </div>
      <div
        className="flex items-center gap-1.5 rounded-2xl rounded-bl-md border border-white/[0.07] bg-ink-800 px-4 py-4"
        aria-label="Assistant is responding"
        role="status"
      >
        {[0, 1, 2].map((index) => (
          <span
            key={index}
            className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent-400"
            style={{ animationDelay: `${index * 160}ms` }}
          />
        ))}
      </div>
    </div>
  );
}
