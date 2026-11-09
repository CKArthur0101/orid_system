import { oridAssessmentIsOpen } from "@/lib/orid-week-access";

type AssessmentKind = "pre" | "post";

const ASSESSMENT_EBOOKS: Record<
  AssessmentKind,
  { title: string; href: string }
> = {
  pre: {
    title: "我們不一樣",
    href: "https://storybook.nlpi.edu.tw/playbook2.aspx?NO=39",
  },
  post: {
    title: "最後才懂",
    href: "https://storybook.nlpi.edu.tw/playbook2.aspx?NO=27",
  },
};

const COPY: Record<
  AssessmentKind,
  { eyebrow: string; heading: string; hint: string; cta: string }
> = {
  pre: {
    eyebrow: "前測",
    heading: "前測閱讀",
    hint: "開始第 1 週寫作前，先打開電子書閱讀。",
    cta: "打開電子書 →",
  },
  post: {
    eyebrow: "後測",
    heading: "後測閱讀",
    hint: "全部週次結束後，再打開電子書閱讀。",
    cta: "打開電子書 →",
  },
};

export function AssessmentEbookCard({ kind }: { kind: AssessmentKind }) {
  const copy = COPY[kind];
  const book = ASSESSMENT_EBOOKS[kind];
  const open = oridAssessmentIsOpen(kind);
  const shellClass = [
    "kid-shell flex min-h-[120px] w-full max-w-xl overflow-hidden",
    open
      ? "cursor-pointer transition-all hover:scale-[1.01] hover:border-amber-600/40 hover:shadow-lg active:scale-[0.99]"
      : "border-dashed border-amber-500/35 opacity-90",
  ].join(" ");

  const body = (
    <div className="flex min-w-0 flex-1 flex-col justify-between gap-2.5 p-3.5 sm:gap-3 sm:p-4 lg:p-5">
      <div>
        <p
          className={`text-xs font-semibold uppercase tracking-wide sm:text-sm ${
            open ? "text-amber-700" : "text-amber-800/55"
          }`}
        >
          {copy.eyebrow}
        </p>
        <p
          className={`mt-1 text-base font-bold leading-snug md:text-[15px] lg:text-lg ${
            open ? "text-amber-950" : "text-amber-950/70"
          }`}
        >
          {copy.heading}
        </p>
        <p
          className={`mt-1 text-sm font-semibold md:text-[13px] lg:text-base ${
            open ? "text-amber-800/80" : "text-amber-800/55"
          }`}
        >
          《{book.title}》
        </p>
        <p className={`mt-1 text-xs sm:text-sm ${open ? "text-amber-900/55" : "text-amber-900/45"}`}>
          {open ? copy.hint : "尚未開放・請等老師通知"}
        </p>
      </div>
      {open ? (
        <span
          className="inline-flex w-fit rounded-full border-2 border-[#5c3215] px-3.5 py-1.5 text-sm font-semibold text-[#fff8f0] sm:px-4 sm:py-2 sm:text-base"
          style={{ backgroundColor: "#7a431d" }}
        >
          {copy.cta}
        </span>
      ) : (
        <span className="inline-flex w-fit rounded-full border-2 border-dashed border-amber-500/40 bg-amber-50/50 px-3.5 py-1.5 text-sm font-semibold text-amber-800/55 sm:px-4 sm:py-2 sm:text-base">
          🔒 尚未開放
        </span>
      )}
    </div>
  );

  if (!open) {
    return (
      <div className={shellClass} aria-label={`${copy.heading}：尚未開放`} aria-disabled="true">
        {body}
      </div>
    );
  }

  return (
    <a
      href={book.href}
      target="_blank"
      rel="noopener noreferrer"
      className={shellClass}
      aria-label={`${copy.heading}：電子書《${book.title}》`}
    >
      {body}
    </a>
  );
}
