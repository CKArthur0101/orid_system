import type { MissionStageKey } from "@/lib/orid-mission-copy";
import { BookIllustration } from "@/components/orid/BookIllustration";
import { ORID_STAGE_THEME } from "@/lib/orid-stage-theme";
import { getBookWeekArt } from "@/lib/orid-book-art";
import { OridMissionProgress } from "@/components/orid/OridMissionProgress";

type StageMissionStatus = "not_started" | "drafting" | "feedback" | "passed";

type StageProgress = {
  stage: MissionStageKey;
  status: StageMissionStatus;
};

export function OridWeekHero({
  weekNum,
  bookTitle,
  focusStage,
  progress,
  writtenCount,
  onFocusStage,
  loading,
  error,
  showAdminControls,
  onRestart,
  restartDisabled,
  className,
}: {
  weekNum: number;
  bookTitle?: string;
  focusStage: MissionStageKey;
  progress: StageProgress[];
  writtenCount: number;
  onFocusStage: (stage: MissionStageKey) => void;
  loading?: boolean;
  error?: string | null;
  showAdminControls?: boolean;
  onRestart?: () => void;
  restartDisabled?: boolean;
  className?: string;
}) {
  const focusTheme = ORID_STAGE_THEME[focusStage];
  const subtitle =
    weekNum === 1 ? "第 1 週｜完成四個反思小任務" : `第 ${weekNum} 週｜先寫作（左）→ 回饋夥伴（右）`;
  const hasBookArt = !!getBookWeekArt(weekNum);

  return (
    <div
      className={[
        "orid-week-hero w-full shrink-0 overflow-hidden rounded-2xl border border-amber-200/70 bg-gradient-to-r from-[#faf5eb] via-[#fffcf7] to-amber-50/30 shadow-sm",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <div className="flex w-full gap-3 px-3 py-2.5 sm:px-4 sm:py-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <h1 className="text-base font-bold leading-tight text-amber-950 sm:text-lg">{subtitle}</h1>
              {bookTitle ? (
                <p className="mt-0.5 truncate text-sm font-semibold text-amber-800 sm:text-base">《{bookTitle}》</p>
              ) : null}
              <p className="mt-1 text-xs text-amber-900/70">
                現在專注：
                <span className={`ml-1 font-semibold ${focusTheme.titleColor}`}>
                  {focusStage} {focusTheme.shortLabel}
                </span>
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              {loading ? <span className="text-xs text-amber-800/70">初始化中…</span> : null}
              {error ? <span className="rounded-lg bg-red-100 px-2 py-0.5 text-xs text-red-700">{error}</span> : null}
              {showAdminControls && onRestart ? (
                <button
                  type="button"
                  onClick={onRestart}
                  disabled={restartDisabled}
                  className="rounded-lg border border-amber-200 bg-white px-2 py-0.5 text-xs font-medium text-amber-900 shadow-sm hover:bg-amber-50 disabled:opacity-50"
                  title="開新 session、清空聊天與寫作（僅實驗管理員）"
                >
                  重新開始本週
                </button>
              ) : null}
            </div>
          </div>
          {weekNum <= 2 ? (
            <div className="mt-2 min-w-0 overflow-x-auto rounded-xl border border-amber-100 bg-white/85 px-2 py-1.5 sm:px-3 sm:py-2">
              <OridMissionProgress
                progress={progress}
                writtenCount={writtenCount}
                onFocusStage={onFocusStage}
                focusStage={focusStage}
                week={weekNum}
              />
            </div>
          ) : null}
        </div>

        {hasBookArt ? (
          <div className="hidden aspect-square w-[7.5rem] shrink-0 sm:block md:w-[9.5rem] lg:w-[11rem]">
            <BookIllustration week={weekNum} variant="scene" layout="hero" className="h-full w-full" />
          </div>
        ) : null}
      </div>
    </div>
  );
}
