import type { ParsedFeedbackNarration } from "@/lib/parse-feedback-narration";
import { PersimmonBullet } from "@/components/orid/PersimmonBullet";

// ── Revision card sections ───────────────────────────────────────────────────

type RevisionSection = {
  key: "praise" | "rethink" | "example";
  label: string;
  panelClass: string;
};

const REVISION_SECTIONS: RevisionSection[] = [
  {
    key: "praise",
    label: "① 你已經做到",
    panelClass: "bg-emerald-50/80 border-emerald-100/80",
  },
  {
    key: "rethink",
    label: "② 這次先修改",
    panelClass: "bg-amber-50/70 border-amber-100/80",
  },
  {
    key: "example",
    label: "③ 可以這樣開始",
    panelClass: "bg-sky-50/70 border-sky-100/80",
  },
];

// ── Complete card sections ───────────────────────────────────────────────────

type CompleteSection = {
  key: "praise" | "completion" | "nextStep";
  label: string;
  panelClass: string;
};

const COMPLETE_SECTIONS: CompleteSection[] = [
  {
    key: "praise",
    label: "① 你已經做到",
    panelClass: "bg-emerald-50/80 border-emerald-100/80",
  },
  {
    key: "completion",
    label: "② 本階段完成",
    panelClass: "bg-emerald-100/70 border-emerald-200/80",
  },
  {
    key: "nextStep",
    label: "③ 下一步",
    panelClass: "bg-sky-50/70 border-sky-100/80",
  },
];

// ── Component ────────────────────────────────────────────────────────────────

export function FeedbackGuideCard({
  parsed,
  section3Label,
}: {
  parsed: ParsedFeedbackNarration;
  /** Override the third-section label for revision cards (e.g. synthesis view). */
  section3Label?: string;
}) {
  if (parsed.kind === "complete") {
    const sections = parsed.nextStep
      ? COMPLETE_SECTIONS
      : COMPLETE_SECTIONS.filter((s) => s.key !== "nextStep");

    return (
      <div className="w-full max-w-full overflow-hidden rounded-2xl border border-emerald-300/80 bg-white shadow-sm lg:max-w-[22rem]">
        <div className="flex flex-col gap-0.5 p-2">
          {sections.map((section) => {
            const value =
              section.key === "praise"
                ? parsed.praise
                : section.key === "completion"
                  ? parsed.completion
                  : parsed.nextStep;
            if (!value) return null;
            return (
              <div
                key={section.key}
                className={`rounded-xl border p-2.5 text-sm leading-relaxed text-amber-950 ${section.panelClass}`}
              >
                <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-emerald-800/80">
                  <PersimmonBullet size={18} />
                  <span>{section.label}</span>
                </div>
                <div className="max-h-[5.5rem] overflow-y-auto whitespace-pre-wrap pl-0.5 text-xs leading-snug md:max-h-[6rem] md:text-sm md:leading-relaxed">
                  {value}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // revision card
  const baseSections = REVISION_SECTIONS.map((s) =>
    section3Label && s.key === "example" ? { ...s, label: section3Label } : s,
  );
  // Don't render empty example section
  const sections = baseSections.filter((s) => {
    if (s.key === "example" && !parsed.example) return false;
    return true;
  });

  return (
    <div className="w-full max-w-full overflow-hidden rounded-2xl border border-amber-200/80 bg-white shadow-sm lg:max-w-[22rem]">
      <div className="flex flex-col gap-0.5 p-2">
        {sections.map((section) => {
          const value =
            section.key === "praise"
              ? parsed.praise
              : section.key === "rethink"
                ? parsed.rethink
                : parsed.example;
          if (!value) return null;
          return (
            <div
              key={section.key}
              className={`rounded-xl border p-2.5 text-sm leading-relaxed text-amber-950 ${section.panelClass}`}
            >
              <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-amber-900/80">
                <PersimmonBullet size={18} />
                <span>{section.label}</span>
              </div>
              <div className="max-h-[5.5rem] overflow-y-auto whitespace-pre-wrap pl-0.5 text-xs leading-snug md:max-h-[6rem] md:text-sm md:leading-relaxed">
                {value}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
