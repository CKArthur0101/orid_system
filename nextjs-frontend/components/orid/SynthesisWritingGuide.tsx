"use client";

const STEPS: {
  step: string;
  title: string;
  desc: string;
  starters: string[];
}[] = [
  {
    step: "開頭",
    title: "先說故事裡發生了什麼",
    desc: "先簡單說明故事中讓你印象最深的那件事。",
    starters: ["故事裡讓我印象最深的是……"],
  },
  {
    step: "中間一",
    title: "寫出你的感受",
    desc: "寫出你看到這件事時的感覺，以及為什麼。",
    starters: ["看到這件事時，我覺得……，因為……"],
  },
  {
    step: "中間二",
    title: "寫出你的想法或體會",
    desc: "寫你從這個故事想到什麼，或學到了什麼。",
    starters: ["這讓我想到……", "我從這個故事學到……"],
  },
  {
    step: "結尾",
    title: "說說你以後想怎麼做",
    desc: "寫你遇到類似情況時，打算怎麼做。",
    starters: ["以後如果我遇到類似的情況，我會……"],
  },
];

export function SynthesisWritingGuide() {
  return (
    <div className="shrink-0 rounded-2xl border border-sky-100 bg-sky-50/50 p-3 sm:p-4">
      <div className="mb-1 flex items-center gap-1.5">
        <span className="text-base" aria-hidden>
          🌰
        </span>
        <span className="text-sm font-bold text-sky-950">這週要做什麼？</span>
      </div>
      <p className="mb-3 text-[12px] leading-relaxed text-sky-900/70">
        這週的任務是把你上週完成的 O、R、I、D 四個想法，整理成一篇完整的反思短文。你不是要重新寫一次
        ORID，而是要把上週的想法接起來，變成一篇有開頭、中間和結尾的文章。
      </p>
      <div className="flex flex-col gap-2">
        {STEPS.map(({ step, title, desc, starters }) => (
          <div
            key={step}
            className="rounded-xl border border-sky-100 bg-white px-3 py-2"
          >
            <div className="mb-0.5 flex items-baseline gap-1.5">
              <span className="inline-flex h-5 min-w-[2.5rem] items-center justify-center rounded-full bg-sky-100 px-1.5 text-[10px] font-bold text-sky-800">
                {step}
              </span>
              <span className="text-[12px] font-semibold text-sky-950">
                {title}
              </span>
            </div>
            <p className="mb-1 text-[11px] leading-snug text-sky-900/55">
              {desc}
            </p>
            <div className="flex flex-col gap-0.5">
              {starters.map((s) => (
                <div
                  key={s}
                  className="rounded-lg bg-sky-50 px-2 py-1 text-[11px] leading-relaxed text-sky-900/75"
                >
                  {s}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      <p className="mt-2 text-[11px] italic text-sky-900/45">
        這些是句型提示，你還是要用自己的話完成整篇文章。
      </p>
    </div>
  );
}
