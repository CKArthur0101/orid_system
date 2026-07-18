import type { ParsedFeedbackNarration } from "@/lib/parse-feedback-narration";
import { PersimmonBullet } from "@/components/orid/PersimmonBullet";

const BASE_SECTIONS: { key: keyof ParsedFeedbackNarration; label: string; panelClass: string }[] = [
  {
    key: "praise",
    label: "① 你已經做到",
    panelClass: "bg-emerald-50/80 border-emerald-100/80",
  },
  {
    key: "rethink",
    label: "② 再想一想",
    panelClass: "bg-amber-50/70 border-amber-100/80",
  },
  {
    key: "example",
    label: "③ 試著補一句",
    panelClass: "bg-sky-50/70 border-sky-100/80",
  },
];

export function FeedbackGuideCard({
  parsed,
  section3Label,
}: {
  parsed: ParsedFeedbackNarration;
  section3Label?: string;
}) {
  const SECTIONS = section3Label
    ? BASE_SECTIONS.map((s) =>
        s.key === "example" ? { ...s, label: section3Label } : s,
      )
    : BASE_SECTIONS;
  return (
    <div className="w-full max-w-full overflow-hidden rounded-2xl border border-amber-200/80 bg-white shadow-sm lg:max-w-[22rem]">
      <div className="flex flex-col gap-0.5 p-2">
        {SECTIONS.map((section) => (
          <div
            key={section.key}
            className={`rounded-xl border p-2.5 text-sm leading-relaxed text-amber-950 ${section.panelClass}`}
          >
            <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-amber-900/80">
              <PersimmonBullet size={18} />
              <span>{section.label}</span>
            </div>
            <div className="max-h-[5.5rem] overflow-y-auto whitespace-pre-wrap pl-0.5 text-xs leading-snug md:max-h-[6rem] md:text-sm md:leading-relaxed">
              {parsed[section.key]}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
