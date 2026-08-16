"use client";

import { useState } from "react";
import { BADGE_CONFIG, BADGE_ORDER, type BadgeId } from "@/lib/orid/badgeRules";

interface BadgeDisplayProps {
  earnedBadges: BadgeId[];
  badgeIds?: BadgeId[];
  size?: number;
  className?: string;
}

/** 未解鎖徽章：統一灰色圓圈樣式，不載入 SVG（避免破圖） */
function LockedBadgeCircle({ size }: { size: number }) {
  const inner = Math.max(12, size - 8);
  return (
    <span
      className="flex items-center justify-center rounded-full bg-amber-50/70 ring-1 ring-amber-200/50"
      style={{ width: inner, height: inner }}
      aria-hidden
    >
      <span
        className="block rounded-full bg-amber-200/35"
        style={{ width: inner * 0.55, height: inner * 0.55 }}
      />
    </span>
  );
}

export function BadgeDisplay({ earnedBadges, badgeIds = BADGE_ORDER, size = 32, className }: BadgeDisplayProps) {
  const [openTooltip, setOpenTooltip] = useState<BadgeId | null>(null);
  const [brokenIds, setBrokenIds] = useState<Set<BadgeId>>(new Set());
  const earnedSet = new Set(earnedBadges);

  function toggleTooltip(id: BadgeId) {
    setOpenTooltip((prev) => (prev === id ? null : id));
  }

  function markBroken(id: BadgeId) {
    setBrokenIds((prev) => {
      if (prev.has(id)) return prev;
      const next = new Set(prev);
      next.add(id);
      return next;
    });
  }

  return (
    <div
      className={["flex shrink-0 flex-nowrap items-center gap-1.5", className].join(" ")}
      role="list"
      aria-label="反思徽章"
    >
      {badgeIds.map((id) => {
        const config = BADGE_CONFIG[id];
        const earned = earnedSet.has(id);
        const isOpen = openTooltip === id;
        const imgBroken = brokenIds.has(id);

        return (
          <div key={id} className="relative shrink-0" role="listitem">
            <button
              type="button"
              aria-label={`${config.name} - ${earned ? "已獲得" : "尚未解鎖"}`}
              aria-expanded={isOpen}
              title={config.name}
              className={[
                "relative flex items-center justify-center rounded-full transition",
                earned
                  ? "ring-2 ring-amber-300 bg-amber-50"
                  : "ring-1 ring-amber-200/60 bg-white/80",
                "hover:ring-amber-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400",
              ].join(" ")}
              style={{ width: size, height: size }}
              onMouseEnter={() => setOpenTooltip(id)}
              onMouseLeave={() => setOpenTooltip(null)}
              onClick={() => toggleTooltip(id)}
            >
              {earned && !imgBroken ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={config.svgPath}
                  alt=""
                  width={size - 4}
                  height={size - 4}
                  className="rounded-full object-contain"
                  draggable={false}
                  onError={() => markBroken(id)}
                />
              ) : earned ? (
                <span
                  className="text-[10px] font-bold text-amber-800"
                  aria-hidden
                >
                  {id === "badge_start"
                    ? "筆"
                    : id === "badge_30"
                      ? "銅"
                      : id === "badge_60"
                        ? "銀"
                        : id === "badge_90"
                          ? "金"
                          : "整"}
                </span>
              ) : (
                <LockedBadgeCircle size={size} />
              )}
            </button>

            {isOpen && (
              <div
                className="pointer-events-auto absolute right-0 top-full z-[200] mt-1.5 w-56 rounded-xl border border-amber-200 bg-white p-2.5 text-[11px] leading-snug shadow-xl sm:w-64"
                onMouseEnter={() => setOpenTooltip(id)}
                onMouseLeave={() => setOpenTooltip(null)}
              >
                <div className="mb-1 font-bold text-amber-950">{config.name}</div>
                {earned ? (
                  <>
                    <div className="mb-0.5 font-medium text-emerald-700">✓ 已獲得</div>
                    <div className="text-amber-900/70">{config.earnedHint}</div>
                  </>
                ) : (
                  <>
                    <div className="mb-0.5 font-medium text-amber-700">🔒 尚未解鎖</div>
                    <div className="text-amber-900/70">{config.unlockHint}</div>
                  </>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
