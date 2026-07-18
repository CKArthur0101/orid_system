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
  compact,
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
  /** 整合寫作三欄版面：縮小 hero，騰出左欄寫作高度（平板實驗用） */
  compact?: boolean;
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
      <div
        className={[
          "flex w-full gap-3",
          compact ? "px-2 py-2" : "px-3 py-2.5 sm:px-4 sm:py-3 md:px-2 md:py-1.5 lg:px-4 lg:py-3",
        ].join(" ")}
      >
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <h1
                className={[
                  "font-bold leading-tight text-amber-950",
                  compact ? "text-sm" : "text-base sm:text-lg md:text-sm lg:text-lg",
                ].join(" ")}
              >
                {subtitle}
              </h1>
              {bookTitle ? (
                <p
                  className={[
                    "mt-0.5 truncate font-semibold text-amber-800",
                    compact ? "text-xs" : "text-sm sm:text-base md:text-xs lg:text-base",
                  ].join(" ")}
                >
                  《{bookTitle}》
                </p>
              ) : null}
              <p
                className={[
                  "mt-0.5 text-amber-900/70 md:mt-0",
                  compact ? "text-[10px]" : "text-xs md:text-[10px] lg:text-xs",
                ].join(" ")}
              >
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
            <div
              className={[
                "mt-1.5 min-w-0 overflow-x-auto rounded-xl border border-amber-100 bg-white/85 md:mt-1 lg:mt-2",
                compact ? "px-1.5 py-1" : "px-2 py-1.5 sm:px-3 sm:py-2 md:px-1.5 md:py-1 lg:px-3 lg:py-2",
              ].join(" ")}
            >
              <OridMissionProgress
                progress={progress}
                writtenCount={writtenCount}
                onFocusStage={onFocusStage}
                focusStage={focusStage}
                week={weekNum}
                compact={compact}
                tabletTight={!compact}
              />
            </div>
          ) : null}
        </div>

        {hasBookArt && !compact ? (
          <div className="hidden aspect-square w-[11rem] shrink-0 lg:block">
            <BookIllustration week={weekNum} variant="scene" layout="hero" className="h-full w-full" />
          </div>
        ) : null}
      </div>
    </div>
  );
}
