"use client";

import { useState } from "react";
import { BADGE_CONFIG, type BadgeId } from "@/lib/orid/badgeRules";

interface BadgeModalProps {
  badgeId: BadgeId;
  onClose: () => void;
}

export function BadgeModal({ badgeId, onClose }: BadgeModalProps) {
  const config = BADGE_CONFIG[badgeId];
  const [imgBroken, setImgBroken] = useState(false);
  if (!config) return null;

  const fallbackLabel =
    badgeId === "badge_start"
      ? "筆"
      : badgeId === "badge_30"
        ? "銅"
        : badgeId === "badge_60"
          ? "銀"
          : "金";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-[min(92vw,24rem)] max-h-[90dvh] overflow-y-auto rounded-2xl bg-white p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="absolute inset-x-0 top-0 flex justify-around px-4 py-2 text-xl opacity-70 pointer-events-none select-none">
          <span>🎉</span>
          <span>✨</span>
          <span>🌟</span>
          <span>✨</span>
          <span>🎉</span>
        </div>

        <div className="mt-4 flex justify-center">
          {imgBroken ? (
            <div className="flex h-24 w-24 items-center justify-center rounded-full bg-amber-50 text-2xl font-bold text-amber-800 ring-2 ring-amber-300">
              {fallbackLabel}
            </div>
          ) : (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={config.svgPath}
              alt={config.name}
              width={96}
              height={96}
              className="drop-shadow-md"
              draggable={false}
              onError={() => setImgBroken(true)}
            />
          )}
        </div>

        <h2 className="mt-4 text-center text-lg font-bold text-amber-950 sm:text-xl">
          {config.modalTitle}
        </h2>

        <p className="mt-2 text-center text-sm leading-relaxed text-amber-900/75">
          {config.modalText}
        </p>

        <div className="mt-6 flex justify-center">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl bg-amber-500 px-6 py-2.5 text-sm font-bold text-white shadow hover:bg-amber-600 active:scale-95"
          >
            繼續寫作
          </button>
        </div>
      </div>
    </div>
  );
}
