import type { ParsedFeedbackNarration } from "@/lib/parse-feedback-narration";

export function FeedbackGuideCard({ parsed }: { parsed: ParsedFeedbackNarration }) {
  return (
    <div className="max-w-[min(92%,28rem)] space-y-2 rounded-2xl border border-sky-200 bg-white p-3 text-sm text-slate-700 shadow-sm">
      <div className="kid-box kid-box-blue !p-2.5">
        <div className="mb-1 text-xs font-bold text-sky-700 sm:text-sm">你已經做到</div>
        <div className="whitespace-pre-wrap leading-relaxed">{parsed.praise}</div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-2.5">
        <div className="mb-1 text-xs font-bold text-slate-700 sm:text-sm">再想一想</div>
        <div className="whitespace-pre-wrap leading-relaxed">{parsed.rethink}</div>
      </div>

      <div className="kid-hint-panel !p-2.5">
        <div className="mb-1 text-xs font-bold text-amber-700 sm:text-sm">可以這樣開始</div>
        <div className="whitespace-pre-wrap leading-relaxed">{parsed.example}</div>
      </div>
    </div>
  );
}
