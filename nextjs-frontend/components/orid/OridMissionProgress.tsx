import type { MissionStageKey } from "@/lib/orid-mission-copy";
import { PersimmonBullet } from "@/components/orid/PersimmonBullet";
import { ORID_STAGE_THEME, STAGE_STATUS_BADGE } from "@/lib/orid-stage-theme";

type StageMissionStatus = "not_started" | "drafting" | "feedback" | "passed";

type StageProgress = {
  stage: MissionStageKey;
  status: StageMissionStatus;
};

const STATUS_LABEL: Record<StageMissionStatus, string> = {
  not_started: "尚未開始",
  drafting: "進行中",
  feedback: "已回饋",
  passed: "已完成",
};

const STAGE_STEP_LABEL: Record<MissionStageKey, string> = {
  O: "觀察",
  R: "感受",
  I: "意義",
  D: "行動",
};

export function OridMissionProgress({
  progress,
  writtenCount,
  onFocusStage,
  focusStage,
}: {
  progress: StageProgress[];
  writtenCount: number;
  onFocusStage: (stage: MissionStageKey) => void;
  focusStage?: MissionStageKey;
}) {
  return (
    <div className="flex flex-wrap items-center gap-1 sm:gap-1.5">
      {progress.map((item, idx) => {
        const theme = ORID_STAGE_THEME[item.stage];
        const active = focusStage === item.stage;
        const done = item.status === "passed";
        return (
          <div key={item.stage} className="flex items-center gap-1">
            {idx > 0 ? (
              <span className="px-0.5 text-xs text-amber-300" aria-hidden>
                →
              </span>
            ) : null}
            <button
              type="button"
              onClick={() => onFocusStage(item.stage)}
              className={[
                "inline-flex min-h-[34px] items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-semibold transition-all sm:min-h-[40px] sm:gap-2 sm:px-2.5 sm:py-1 sm:text-xs",
                done
                  ? "border-emerald-400 bg-emerald-50 text-emerald-900"
                  : active
                    ? theme.statusActive
                    : STAGE_STATUS_BADGE[item.status],
              ].join(" ")}
              aria-label={`切換到 ${item.stage} ${theme.shortLabel}`}
            >
              <PersimmonBullet size={24} />
              <span>{STAGE_STEP_LABEL[item.stage]}</span>
              <span className="font-normal opacity-80">{STATUS_LABEL[item.status]}</span>
            </button>
          </div>
        );
      })}
      <span className="ml-auto text-[10px] font-medium text-amber-900/70 sm:text-xs">已寫 {writtenCount} / 4</span>
    </div>
  );
}
