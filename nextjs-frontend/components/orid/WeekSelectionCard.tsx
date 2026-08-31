import Image from "next/image";
import Link from "next/link";
import { SYSTEM_ILLUSTRATIONS } from "@/lib/orid-system-art";
import { OridStageDots, type StageState } from "@/components/orid/OridStageDots";
import type { OridStageKey } from "@/lib/orid-stage-theme";
import { ORID_BADGE_ORDER, SYNTHESIS_BADGE_ORDER } from "@/lib/orid/badgeRules";

interface WeekSelectionCardProps {
  week: number;
  title?: string;
  coverThumb?: string;
  locked?: boolean;
  earnedBadges?: string[];
  stageStates?: Partial<Record<OridStageKey, StageState>>;
}

function CardBody({
  week,
  title,
  coverThumb,
  locked,
  earnedBadges,
  stageStates,
}: WeekSelectionCardProps) {
  const thumbSrc = coverThumb ?? SYSTEM_ILLUSTRATIONS.reading;
  const expectedBadgeIds = week % 2 === 0 ? SYNTHESIS_BADGE_ORDER : ORID_BADGE_ORDER;
  const earnedBadgeSet = new Set(earnedBadges ?? []);
  const earnedBadgeCount = expectedBadgeIds.filter((id) => earnedBadgeSet.has(id)).length;
  const hasBadges = earnedBadgeCount > 0;

  return (
    <>
      <div className="flex min-w-0 flex-1 flex-col justify-between gap-3 p-4 sm:p-5">
        <div>
          <p
            className={`text-xs font-semibold uppercase tracking-wide sm:text-sm ${
              locked ? "text-amber-800/45" : "text-amber-700"
            }`}
          >
            第 {week} 週
          </p>
          <p
            className={`mt-1 text-base font-bold leading-snug sm:text-lg ${
              locked ? "text-amber-900/50" : "text-amber-950"
            }`}
          >
            {locked ? "尚未開放" : title ? `《${title}》` : "故事即將公布"}
          </p>
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
              <span className="rounded-full border border-emerald-400/40 bg-emerald-100/80 px-2.5 py-0.5 text-xs font-bold text-emerald-800">
                🏅 × {earnedBadgeCount}
              </span>
            ) : (
              <span className="rounded-full border border-amber-400/35 bg-amber-50/80 px-2.5 py-0.5 text-xs font-semibold text-amber-800">
                已開放 →
              </span>
            )}
          </div>
        ) : null}
      </div>

      <div className="flex w-[84px] shrink-0 items-center justify-center p-2 sm:w-[96px] md:w-[108px]">
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
            className="h-auto max-h-[96px] w-full object-contain drop-shadow-sm sm:max-h-[104px]"
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
      href={`/dashboard/books/week/${props.week}`}
      className={`${shellClass} cursor-pointer hover:scale-[1.01]`}
    >
      <CardBody {...props} />
    </Link>
  );
}
