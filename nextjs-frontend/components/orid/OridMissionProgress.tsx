import type { MissionStageKey } from "@/lib/orid-mission-copy";

type StageMissionStatus = "not_started" | "drafting" | "feedback" | "passed";

type StageProgress = {
  stage: MissionStageKey;
  status: StageMissionStatus;
};

const STATUS_LABEL: Record<StageMissionStatus, string> = {
  not_started: "尚未開始",
  drafting: "進行中",
  feedback: "已回饋",
  passed: "已通過",
};

const STATUS_CLASS: Record<StageMissionStatus, string> = {
  not_started: "border-slate-200 bg-slate-50 text-slate-500",
  drafting: "border-sky-200 bg-sky-50 text-sky-700",
  feedback: "border-amber-200 bg-amber-50 text-amber-700",
  passed: "border-emerald-200 bg-emerald-50 text-emerald-700",
};

export function OridMissionProgress({
  progress,
  writtenCount,
  onFocusStage,
}: {
  progress: StageProgress[];
  writtenCount: number;
  onFocusStage: (stage: MissionStageKey) => void;
}) {
  return (
    <div className="mt-1 rounded-xl border border-sky-100 bg-sky-50/40 px-2 py-1.5 text-[11px] text-slate-700 sm:px-3 sm:py-2 sm:text-xs">
      <div className="mb-1 font-medium">今天的反思任務：已寫 {writtenCount} / 4</div>
      <div className="flex flex-wrap gap-1.5">
        {progress.map((item) => (
          <button
            key={item.stage}
            type="button"
            onClick={() => onFocusStage(item.stage)}
            className={[
              "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 transition hover:brightness-95",
              STATUS_CLASS[item.status],
            ].join(" ")}
            aria-label={`切換到 ${item.stage} 任務`}
          >
            <span className="font-semibold">{item.stage}</span>
            <span>{STATUS_LABEL[item.status]}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
