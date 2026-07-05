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

const STAGE_DOT_COLORS: Record<MissionStageKey, string> = {
  O: "#6aaee0",
  R: "#e8a84d",
  I: "#66b88f",
  D: "#9f88cf",
};

function StageDot({ stage, size = 20 }: { stage: MissionStageKey; size?: number }) {
  return (
    <span
      className="shrink-0 rounded-full"
      style={{
        width: size,
        height: size,
        minWidth: size,
        minHeight: size,
        backgroundColor: STAGE_DOT_COLORS[stage],
        display: "inline-block",
      }}
      aria-hidden
    />
  );
}

export function OridMissionProgress({
  progress,
  writtenCount,
  onFocusStage,
  focusStage,
  week,
}: {
  progress: StageProgress[];
  writtenCount: number;
  onFocusStage: (stage: MissionStageKey) => void;
  focusStage?: MissionStageKey;
  week?: number;
}) {
  const usePersimmon = week === 1;
  const bulletSize = usePersimmon ? 18 : 16;

  return (
    <div className="flex min-w-0 flex-nowrap items-center gap-1 overflow-x-auto pb-0.5 [-ms-overflow-style:none] [scrollbar-width:none] sm:gap-1.5 md:gap-1 [&::-webkit-scrollbar]:hidden">
      {progress.map((item, idx) => {
        const theme = ORID_STAGE_THEME[item.stage];
        const active = focusStage === item.stage;
        const done = item.status === "passed";
        return (
          <div key={item.stage} className="flex shrink-0 items-center gap-0.5 sm:gap-1">
            {idx > 0 ? (
              <span className="px-0.5 text-[10px] text-amber-300 sm:text-xs" aria-hidden>
                →
              </span>
            ) : null}
            <button
              type="button"
              onClick={() => onFocusStage(item.stage)}
              className={[
                "inline-flex shrink-0 items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-semibold transition-all",
                "min-h-[32px] md:min-h-[34px] lg:min-h-[40px] lg:gap-2 lg:px-2.5 lg:py-1 lg:text-xs",
                done
                  ? "border-emerald-400 bg-emerald-50 text-emerald-900"
                  : active
                    ? theme.statusActive
                    : STAGE_STATUS_BADGE[item.status],
              ].join(" ")}
              aria-label={`切換到 ${item.stage} ${theme.shortLabel}`}
            >
              {usePersimmon ? (
                <PersimmonBullet size={bulletSize} />
              ) : (
                <StageDot stage={item.stage} size={bulletSize} />
              )}
              <span className="whitespace-nowrap">{STAGE_STEP_LABEL[item.stage]}</span>
              <span className="hidden whitespace-nowrap font-normal opacity-80 sm:inline">
                {STATUS_LABEL[item.status]}
              </span>
            </button>
          </div>
        );
      })}
      <span className="ml-1 shrink-0 whitespace-nowrap pl-1 text-[10px] font-medium text-amber-900/70 sm:ml-auto sm:pl-0 sm:text-xs">
        已寫 {writtenCount} / 4
      </span>
    </div>
  );
}
