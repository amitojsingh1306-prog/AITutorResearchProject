import { useEffect, useState } from "react";

import { memoryApi, type MemoryDebugResponse } from "../api/memoryApi";
import { CloseIcon } from "./Icons";

interface MemoryDebugPanelProps {
  onClose: () => void;
}

export function MemoryDebugPanel({ onClose }: MemoryDebugPanelProps) {
  const [data, setData] = useState<MemoryDebugResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    memoryApi
      .debug(10)
      .then((response) => {
        if (!cancelled) setData(response);
      })
      .catch((requestError) => {
        if (!cancelled) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : "Could not load memory embeddings.",
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <aside className="absolute inset-y-0 right-0 z-20 flex w-full max-w-xl flex-col border-l border-white/[0.08] bg-ink-950/95 shadow-2xl backdrop-blur">
      <header className="flex h-16 shrink-0 items-center justify-between border-b border-white/[0.08] px-5">
        <div>
          <p className="text-sm font-semibold text-white">Memory Embeddings</p>
          <p className="text-xs text-slate-500">
            {data
              ? `${data.collection} · ${data.count} indexed`
              : "Loading Chroma preview..."}
          </p>
        </div>
        <button
          type="button"
          aria-label="Close memory debug panel"
          className="rounded-lg p-2 text-slate-500 hover:bg-white/5 hover:text-white"
          onClick={onClose}
        >
          <CloseIcon className="h-5 w-5" />
        </button>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
        {error ? (
          <p className="rounded-lg border border-red-400/20 bg-red-500/10 p-3 text-sm text-red-200">
            {error}
          </p>
        ) : !data ? (
          <div className="flex items-center gap-3 text-sm text-slate-500">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-700 border-t-accent-400" />
            Reading embedding index...
          </div>
        ) : data.items.length === 0 ? (
          <p className="text-sm text-slate-500">
            No embeddings found. Run the JSON-to-Chroma sync script first.
          </p>
        ) : (
          <div className="space-y-3">
            {data.items.map((item) => (
              <article
                key={item.id}
                className="rounded-lg border border-white/[0.08] bg-white/[0.03] p-3"
              >
                <div className="mb-2 flex items-center justify-between gap-3">
                  <p className="truncate text-xs font-medium text-slate-300">
                    {item.metadata.role ?? "message"} · {item.metadata.user_id ?? "user"}
                  </p>
                  <p className="shrink-0 text-xs text-slate-600">
                    {item.embedding_length} dims
                  </p>
                </div>
                <p className="mb-3 line-clamp-3 text-sm leading-6 text-slate-200">
                  {item.document}
                </p>
                <div className="rounded-md bg-ink-900 p-2">
                  <p className="mb-1 text-[11px] uppercase tracking-wide text-slate-600">
                    First 8 values
                  </p>
                  <p className="break-all font-mono text-xs leading-5 text-accent-200">
                    [{item.embedding_preview.map((value) => value.toFixed(4)).join(", ")}]
                  </p>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}
