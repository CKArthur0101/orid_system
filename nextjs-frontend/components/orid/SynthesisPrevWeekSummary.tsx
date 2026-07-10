"use client";

type StageKey = "O" | "R" | "I" | "D";

/** Minimal shape needed — accepts the full OridWritingV1 from page.tsx */
type WithStages = {
  stages: Record<StageKey, { d1: string; d2: string }>;
  [key: string]: unknown;
};

const STAGE_META: Record<
  StageKey,
  { label: string; question: string; fallback: string }
> = {
  O: {
    label: "O 觀察",
    question: "故事中發生了什麼？",
    fallback: "這一段還可以再補充故事中發生了什麼事。",
  },
  R: {
    label: "R 感受",
    question: "我有什麼感覺？",
    fallback: "這一段還可以再補充你的感受和原因。",
  },
  I: {
    label: "I 體悟",
    question: "我想到或學到了什麼？",
    fallback: "這一段還可以再補充你從故事中學到什麼。",
  },
  D: {
    label: "D 行動",
    question: "我以後可以怎麼做？",
    fallback: "這一段還可以再補充你未來想怎麼做。",
  },
};

const STAGES: StageKey[] = ["O", "R", "I", "D"];
const SUMMARY_MIN_LEN = 30;
const SUMMARY_MAX_LEN = 100;

function summarise(text: string): string | null {
  const t = (text ?? "").trim();
  if (t.length < SUMMARY_MIN_LEN) return null;
  return t.length > SUMMARY_MAX_LEN ? t.slice(0, SUMMARY_MAX_LEN) + "…" : t;
}

interface SynthesisPrevWeekSummaryProps {
  week1Data: WithStages;
}

export function SynthesisPrevWeekSummary({
  week1Data,
}: SynthesisPrevWeekSummaryProps) {
  return (
    <div className="shrink-0 rounded-2xl border border-amber-100 bg-amber-50/60 p-3 sm:p-4">
      <div className="mb-3 flex items-center gap-1.5">
        <span className="text-base" aria-hidden>
          📝
        </span>
        <span className="text-sm font-bold text-amber-950">上週想法整理</span>
      </div>
      <div className="flex flex-col gap-2">
        {STAGES.map((key) => {
          const meta = STAGE_META[key];
          const raw = week1Data.stages[key]?.d1 ?? "";
          const summary = summarise(raw);
          return (
            <div
              key={key}
              className="rounded-xl border border-amber-100 bg-white px-3 py-2"
            >
              <div className="mb-0.5 flex items-baseline gap-1.5">
                <span className="text-[11px] font-bold text-amber-800">
                  {meta.label}
                </span>
                <span className="text-[11px] text-amber-900/55">
                  {meta.question}
                </span>
              </div>
              {summary ? (
                <p className="text-[13px] leading-snug text-amber-950/85">
                  {summary}
                </p>
              ) : (
                <p className="text-[12px] italic leading-snug text-amber-900/45">
                  {meta.fallback}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
