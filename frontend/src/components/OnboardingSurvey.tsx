import { useState, type FormEvent } from "react";

import { profileApi } from "../api/profileApi";
import type { LearnerProfile, OnboardingAnswers } from "../types/profile";
import { BookIcon, SendIcon, SparkIcon } from "./Icons";

interface OnboardingSurveyProps {
  userId: string;
  defaultName: string;
  onComplete: (profile: LearnerProfile) => void;
}

type FieldKey = keyof OnboardingAnswers;

interface QuestionDef {
  field: FieldKey;
  prompt: string;
  placeholder: string;
  /** Split the raw answer into a list, for multi-value fields. */
  isList?: boolean;
  optional?: boolean;
}

const QUESTIONS: QuestionDef[] = [
  { field: "name", prompt: "What's your name?", placeholder: "e.g. Prarthana" },
  {
    field: "field_of_study",
    prompt: "What are you studying?",
    placeholder: "e.g. B.Tech CSE, Fintech honors",
  },
  {
    field: "topics_of_interest",
    prompt: "What subjects or topics do you want help with?",
    placeholder: "e.g. DSA, operating systems, ML (comma-separated)",
    isList: true,
  },
  {
    field: "skill_level",
    prompt: "What's your current level in these topics?",
    placeholder: "e.g. beginner, intermediate, advanced",
  },
  {
    field: "preferred_explanation_style",
    prompt: "How do you like explanations best?",
    placeholder: "e.g. step-by-step with examples, visual, high-level first",
  },
  {
    field: "goals",
    prompt: "Any goals for this tutor? (optional)",
    placeholder: "e.g. ace my next exam, build intuition for interviews",
    isList: true,
    optional: true,
  },
];

interface AnsweredEntry {
  prompt: string;
  answer: string;
}

function toAnswers(entries: Record<FieldKey, string>, name: string): OnboardingAnswers {
  const splitList = (value: string) =>
    value
      .split(",")
      .map((item) => item.trim())
      .filter((item) => item.length > 0);

  return {
    name: entries.name.trim() || name,
    field_of_study: entries.field_of_study.trim(),
    topics_of_interest: splitList(entries.topics_of_interest),
    skill_level: entries.skill_level.trim(),
    preferred_explanation_style: entries.preferred_explanation_style.trim(),
    goals: splitList(entries.goals),
  };
}

export function OnboardingSurvey({ userId, defaultName, onComplete }: OnboardingSurveyProps) {
  const [stepIndex, setStepIndex] = useState(0);
  const [draft, setDraft] = useState(defaultName);
  const [answers, setAnswers] = useState<Record<FieldKey, string>>({
    name: "",
    field_of_study: "",
    topics_of_interest: "",
    skill_level: "",
    preferred_explanation_style: "",
    goals: "",
  });
  const [history, setHistory] = useState<AnsweredEntry[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const currentQuestion = QUESTIONS[stepIndex];
  const isLastQuestion = stepIndex === QUESTIONS.length - 1;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = draft.trim();
    if (!trimmed && !currentQuestion.optional) return;

    const updatedAnswers = { ...answers, [currentQuestion.field]: trimmed };
    setAnswers(updatedAnswers);
    setHistory((current) => [
      ...current,
      { prompt: currentQuestion.prompt, answer: trimmed || "(skipped)" },
    ]);
    setDraft("");

    if (!isLastQuestion) {
      setStepIndex((index) => index + 1);
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      const payload = toAnswers(updatedAnswers, defaultName);
      const { profile } = await profileApi.completeOnboarding(userId, payload);
      onComplete(profile);
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Could not save your profile. Please try again.",
      );
      setIsSubmitting(false);
    }
  }

  return (
    <main className="grid min-h-dvh place-items-center bg-ink-900 px-4 py-8 text-slate-100">
      <div className="flex w-full max-w-xl flex-col gap-4">
        <div className="mb-2 flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-xl border border-accent-400/20 bg-accent-500/10 text-accent-400">
            <BookIcon className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-semibold text-white">Quick setup</p>
            <p className="text-xs text-slate-500">
              A few questions so replies feel tailored to you.
            </p>
          </div>
        </div>

        <div className="flex max-h-[50vh] flex-col gap-3 overflow-y-auto rounded-xl border border-white/[0.08] bg-white/[0.03] p-4">
          {history.map((entry, index) => (
            <div key={index} className="flex flex-col gap-2">
              <div className="max-w-[85%] rounded-lg rounded-tl-sm bg-ink-950 px-3 py-2 text-sm text-slate-200">
                {entry.prompt}
              </div>
              <div className="ml-auto max-w-[85%] rounded-lg rounded-tr-sm bg-accent-500/15 px-3 py-2 text-sm text-accent-100">
                {entry.answer}
              </div>
            </div>
          ))}
          <div className="max-w-[85%] rounded-lg rounded-tl-sm bg-ink-950 px-3 py-2 text-sm text-slate-200">
            {currentQuestion.prompt}
          </div>
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}

        <form className="flex items-center gap-2" onSubmit={handleSubmit}>
          <input
            autoFocus
            value={draft}
            disabled={isSubmitting}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={currentQuestion.placeholder}
            className="flex-1 rounded-lg border border-white/[0.08] bg-ink-950 px-3 py-3 text-sm text-white outline-none transition placeholder:text-slate-700 focus:border-accent-400/60 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={isSubmitting}
            className="flex items-center justify-center gap-2 rounded-lg bg-accent-400 px-4 py-3 text-sm font-semibold text-ink-950 transition hover:bg-accent-300 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSubmitting ? (
              <SparkIcon className="h-4 w-4 animate-pulse" />
            ) : (
              <SendIcon className="h-4 w-4" />
            )}
            {isLastQuestion ? "Finish" : "Next"}
          </button>
        </form>

        <p className="text-center text-xs text-slate-600">
          Step {stepIndex + 1} of {QUESTIONS.length}
        </p>
      </div>
    </main>
  );
}
