"use client";

/** Compact static guide (optional embed). Prefer SynthesisScaffoldPanel on the live page. */
const STEPS: { step: string; title: string; starter: string }[] = [
  { step: "1", title: "故事裡的事", starter: "故事裡讓我印象最深的是……" },
  { step: "2", title: "感受＋原因", starter: "看到這件事時，我覺得……，因為……" },
  { step: "3", title: "學到／想到", starter: "這讓我想到……／我學到……" },
  { step: "4", title: "以後怎麼做", starter: "以後如果遇到類似情況，我會……" },
];

export function SynthesisWritingGuide() {
  return (
    <div className="shrink-0 rounded-2xl border border-sky-100 bg-sky-50/50 p-3">
      <div className="mb-1 text-sm font-bold text-sky-950">這週：收成一篇短文</div>
      <p className="mb-2 text-[12px] leading-relaxed text-sky-900/70">
        把上週四格接起來寫，不是重寫四次。對一下清單就好。
      </p>
      <div className="flex flex-col gap-1.5">
        {STEPS.map(({ step, title, starter }) => (
          <div
            key={step}
            className="rounded-xl border border-sky-100 bg-white px-3 py-1.5"
          >
            <div className="text-[12px] font-semibold text-sky-950">
              {step}. {title}
            </div>
            <div className="text-[11px] text-sky-900/70">{starter}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
