import { ORID_STAGE_THEME, type OridStageKey } from "@/lib/orid-stage-theme";

export type StageState = "inactive" | "active" | "done";

export interface OridStageDotsProps {
  /** Per-stage state. Keys not present default to "inactive". */
  stages?: Partial<Record<OridStageKey, StageState>>;
  size?: "sm" | "md";
  className?: string;
}

const STAGE_KEYS: OridStageKey[] = ["O", "R", "I", "D"];

const ACTIVE_COLORS: Record<OridStageKey, string> = {
  O: "#6aaee0",
  R: "#e8a84d",
  I: "#66b88f",
  D: "#9f88cf",
};

export function OridStageDots({
  stages = {},
  size = "sm",
  className,
}: OridStageDotsProps) {
  const dotSize = size === "md" ? "h-4 w-4" : "h-3 w-3";
  const labelSize = size === "md" ? "text-[11px]" : "text-[9px]";

  return (
    <div className={`flex items-center gap-1.5 ${className ?? ""}`}>
      {STAGE_KEYS.map((key) => {
        const state = stages[key] ?? "inactive";
        const color = ACTIVE_COLORS[key];
        const isDone = state === "done";
        const isActive = state === "active";

        return (
          <div key={key} className="flex flex-col items-center gap-0.5">
            <div
              className={[
                `rounded-full ${dotSize} transition-all`,
                isDone
                  ? "ring-1 ring-offset-1"
                  : isActive
                    ? "ring-1 ring-offset-1 ring-amber-200"
                    : "opacity-25",
              ].join(" ")}
              style={
                isDone || isActive
                  ? { backgroundColor: color }
                  : { backgroundColor: "#d4c5a9" }
              }
              title={ORID_STAGE_THEME[key].shortLabel}
              aria-label={`${key} ${ORID_STAGE_THEME[key].shortLabel}: ${state}`}
            />
            <span
              className={`${labelSize} font-bold leading-none`}
              style={{ color: isDone || isActive ? color : "#9e8c74" }}
            >
              {key}
            </span>
          </div>
        );
      })}
    </div>
  );
}
