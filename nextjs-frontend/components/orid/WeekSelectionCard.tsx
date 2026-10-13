import Image from "next/image";
import Link from "next/link";
import { SYSTEM_ILLUSTRATIONS } from "@/lib/orid-system-art";
import { OridStageDots, type StageState } from "@/components/orid/OridStageDots";
import type { OridStageKey } from "@/lib/orid-stage-theme";
import { badgeIdsForWeek, getHomeMedalImagePath } from "@/lib/orid/badgeRules";
import { studentWeekPath } from "@/lib/student-routes";

interface WeekSelectionCardProps {
  week: number;
  title?: string;
  /** Short task label under the title, e.g. 「O・R 觀察與感受」 for week 1. */
  subtitle?: string;
  coverThumb?: string;
  locked?: boolean;
  earnedBadges?: string[];
  stageStates?: Partial<Record<OridStageKey, StageState>>;
}

function CardBody({
  week,
  title,
  subtitle,
  coverThumb,
  locked,
  earnedBadges,
  stageStates,
}: WeekSelectionCardProps) {
  const thumbSrc = coverThumb ?? SYSTEM_ILLUSTRATIONS.reading;
  const expectedBadgeIds = badgeIdsForWeek(week);
  const earnedBadgeSet = new Set(earnedBadges ?? []);
  const earnedBadgeCount = expectedBadgeIds.filter((id) => earnedBadgeSet.has(id)).length;
  const hasBadges = earnedBadgeCount > 0;

  return (
    <>
      <div className="flex min-w-0 flex-1 flex-col justify-between gap-2.5 p-3.5 sm:gap-3 sm:p-4 lg:p-5">
        <div>
          <p
            className={`text-xs font-semibold uppercase tracking-wide sm:text-sm ${
              locked ? "text-amber-800/45" : "text-amber-700"
            }`}
          >
            第 {week} 週
          </p>
          <p
            className={`mt-1 text-base font-bold leading-snug md:text-[15px] md:leading-snug lg:text-lg ${
              locked ? "text-amber-900/50" : "text-amber-950"
            }`}
          >
            {locked ? "尚未開放" : title ? `《${title}》` : "故事即將公布"}
          </p>
          {!locked && subtitle ? (
            <p className="mt-1 text-sm font-semibold text-amber-800/80 md:text-[13px] lg:text-base">{subtitle}</p>
          ) : null}
          {locked ? (
            <p className="mt-1 text-xs text-amber-900/40 sm:text-sm">請等老師通知</p>
          ) : null}
        </div>

        {!locked && stageStates ? (
          <OridStageDots stages={stageStates} size="sm" />
        ) : null}

        {!locked ? (
          <div className="flex flex-wrap items-center gap-2">
            {hasBadges ? (
              <span className="inline-flex items-center gap-2 rounded-full border-2 border-amber-400/50 bg-amber-50/80 py-1.5 pl-1.5 pr-3.5 text-base font-bold text-amber-800 sm:gap-2.5 sm:py-2 sm:pl-2 sm:pr-4 sm:text-lg">
                <Image
                  src={getHomeMedalImagePath(undefined, week)}
                  alt=""
                  width={48}
                  height={48}
                  className="h-11 w-11 object-contain drop-shadow-sm sm:h-12 sm:w-12"
                  aria-hidden
                />
                <span>× {earnedBadgeCount}</span>
              </span>
            ) : (
              <span
                className="rounded-full border-2 border-[#5c3215] px-3.5 py-1.5 text-sm font-semibold text-[#fff8f0] sm:px-4 sm:py-2 sm:text-base"
                style={{ backgroundColor: "#7a431d" }}
              >
                已開放 →
              </span>
            )}
          </div>
        ) : null}
      </div>

      <div className="flex w-[76px] shrink-0 items-center justify-center p-1.5 sm:w-[84px] md:w-[72px] lg:w-[100px] lg:p-2 xl:w-[108px]">
        {locked ? (
          <span className="text-3xl opacity-40 sm:text-4xl" aria-hidden>
            🔒
          </span>
        ) : (
          <Image
            src={thumbSrc}
            alt=""
            width={108}
            height={108}
            className="h-auto max-h-[84px] w-full object-contain drop-shadow-sm md:max-h-[76px] lg:max-h-[100px]"
          />
        )}
      </div>
    </>
  );
}

export function WeekSelectionCard(props: WeekSelectionCardProps) {
  const { locked = false } = props;
  const shellClass = [
    "kid-shell flex h-full min-h-[148px] w-full overflow-hidden",
    locked
      ? "border-dashed border-amber-500/35 opacity-65"
      : "transition-all hover:border-amber-600/40 hover:shadow-lg active:scale-[0.99]",
  ].join(" ");

  if (locked) {
    return (
      <div className={shellClass} aria-label={`第 ${props.week} 週（未開放）`} aria-disabled="true">
        <CardBody {...props} />
      </div>
    );
  }

  return (
    <Link
      href={studentWeekPath(props.week)}
      className={`${shellClass} cursor-pointer hover:scale-[1.01]`}
    >
      <CardBody {...props} />
    </Link>
  );
}
