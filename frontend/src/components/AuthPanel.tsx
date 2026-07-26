import { useState, type FormEvent } from "react";

import type { UserProfile } from "../types/user";
import { BookIcon, SparkIcon } from "./Icons";

interface AuthPanelProps {
  onSubmit: (profile: UserProfile) => void;
}

function userIdFromEmail(email: string): string {
  return email.trim().toLowerCase();
}

export function AuthPanel({ onSubmit }: AuthPanelProps) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [mode, setMode] = useState<"signup" | "signin">("signup");

  const canSubmit = name.trim().length > 0 && email.trim().length > 0;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) return;
    onSubmit({
      id: userIdFromEmail(email),
      name: name.trim(),
      email: email.trim().toLowerCase(),
    });
  }

  return (
    <main className="grid min-h-dvh bg-ink-900 px-4 py-8 text-slate-100">
      <div className="mx-auto grid w-full max-w-5xl items-center gap-8 lg:grid-cols-[1fr_380px]">
        <section className="max-w-2xl">
          <div className="mb-6 grid h-14 w-14 place-items-center rounded-2xl border border-accent-400/20 bg-accent-500/10 text-accent-400 shadow-glow">
            <BookIcon className="h-7 w-7" />
          </div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-accent-300">
            Responsible AI tutor platform
          </p>
          <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-5xl">
            Personal learning history for every student.
          </h1>
          <p className="mt-5 max-w-xl text-sm leading-6 text-slate-400 sm:text-base">
            Sign in before chatting so the tutor can keep each learner&apos;s
            conversations separate. This is a local prototype identity layer,
            ready to be replaced by production authentication later.
          </p>
        </section>

        <section className="rounded-xl border border-white/[0.08] bg-white/[0.04] p-5 shadow-2xl">
          <div className="mb-5 flex rounded-lg border border-white/[0.08] bg-ink-950 p-1">
            <button
              type="button"
              className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition ${
                mode === "signup"
                  ? "bg-accent-500/15 text-accent-300"
                  : "text-slate-500 hover:text-slate-300"
              }`}
              onClick={() => setMode("signup")}
            >
              Sign up
            </button>
            <button
              type="button"
              className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition ${
                mode === "signin"
                  ? "bg-accent-500/15 text-accent-300"
                  : "text-slate-500 hover:text-slate-300"
              }`}
              onClick={() => setMode("signin")}
            >
              Sign in
            </button>
          </div>

          <form className="space-y-4" onSubmit={handleSubmit}>
            <div>
              <label
                htmlFor="name"
                className="text-xs font-medium uppercase tracking-[0.16em] text-slate-500"
              >
                Name
              </label>
              <input
                id="name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                className="mt-2 w-full rounded-lg border border-white/[0.08] bg-ink-950 px-3 py-3 text-sm text-white outline-none transition placeholder:text-slate-700 focus:border-accent-400/60"
                placeholder="Amitoj"
              />
            </div>

            <div>
              <label
                htmlFor="email"
                className="text-xs font-medium uppercase tracking-[0.16em] text-slate-500"
              >
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="mt-2 w-full rounded-lg border border-white/[0.08] bg-ink-950 px-3 py-3 text-sm text-white outline-none transition placeholder:text-slate-700 focus:border-accent-400/60"
                placeholder="student@example.com"
              />
            </div>

            <button
              type="submit"
              disabled={!canSubmit}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent-400 px-4 py-3 text-sm font-semibold text-ink-950 transition hover:bg-accent-300 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <SparkIcon className="h-4 w-4" />
              {mode === "signup" ? "Create learning profile" : "Continue"}
            </button>
          </form>
        </section>
      </div>
    </main>
  );
}
