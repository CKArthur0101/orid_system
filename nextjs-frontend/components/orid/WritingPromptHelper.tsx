"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { PersimmonBullet } from "./PersimmonBullet";
import {
  getControlGuidePages,
  getSynthesisGuidePages,
  type ControlGuidePage,
} from "@/lib/orid/control-guide-pages";

type StageKey = "O" | "R" | "I" | "D";

interface WritingPromptHelperProps {
  focusStage: StageKey;
  onPromptViewed?: () => void;
  /** Week-2 synthesis mode for control group: show synthesis-specific prompts */
  synthesisMode?: boolean;
  /** Personalized opening reference (control group synthesis tab) */
  openingText?: string;
}

export function WritingPromptHelper({
  focusStage,
  onPromptViewed,
  synthesisMode,
  openingText,
}: WritingPromptHelperProps) {
  const pages: ControlGuidePage[] = synthesisMode
    ? getSynthesisGuidePages()
    : getControlGuidePages(focusStage);

  const [pageIndex, setPageIndex] = useState(0);
  const loggedViewRef = useRef(false);

  useEffect(() => {
    setPageIndex(0);
    loggedViewRef.current = false;
  }, [focusStage, synthesisMode]);

  const current = pages[pageIndex] ?? pages[0];
  const total = pages.length;
  const atStart = pageIndex <= 0;
  const atEnd = pageIndex >= total - 1;

  function logViewOnce() {
    if (!loggedViewRef.current) {
      loggedViewRef.current = true;
      onPromptViewed?.();
    }
  }

  function goPrev() {
    if (atStart) return;
    setPageIndex((i) => i - 1);
    logViewOnce();
  }

  function goNext() {
    if (atEnd) return;
    setPageIndex((i) => i + 1);
    logViewOnce();
  }

  if (!current) return null;

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-[#fffcf7]">
      <div className="shrink-0 border-b border-amber-100 px-2.5 py-2 md:px-3 md:py-2.5">
        <div className="flex items-center gap-2">
          <span className="text-lg md:text-xl" aria-hidden>
            🌰
          </span>
          <div className="min-w-0 flex-1">
            <div className="text-xs font-bold text-amber-950 md:text-sm">
              {synthesisMode ? "整合寫作提示" : "寫作提示小幫手"}
            </div>
            <div className="text-[10px] text-amber-900/60 md:text-[11px]">
              一步一步翻頁，幫你想清楚再下筆
            </div>
          </div>
        </div>
        <div className="mt-2 flex items-center justify-between gap-2">
          <span className="shrink-0 text-[10px] font-semibold text-amber-800/80 md:text-xs">
            第 {pageIndex + 1} 步／共 {total} 步
          </span>
          <div className="flex min-w-0 flex-1 justify-end gap-1" aria-hidden>
            {pages.map((_, i) => (
              <span
                key={i}
                className={[
                  "h-2 w-2 rounded-full transition-colors",
                  i === pageIndex ? "bg-amber-500" : i < pageIndex ? "bg-amber-300" : "bg-amber-200/80",
                ].join(" ")}
              />
            ))}
          </div>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden p-2 md:p-3">
        {synthesisMode && openingText && pageIndex === 0 ? (
          <div className="kid-bubble-ai mb-2 shrink-0 border border-amber-100/80 bg-amber-50/40 text-xs leading-relaxed md:text-sm">
            <div className="whitespace-pre-wrap">{openingText}</div>
          </div>
        ) : null}

        <div
          className={[
            "flex min-h-0 flex-1 flex-col justify-center rounded-2xl border-2 p-3 shadow-sm md:p-4",
            current.track === "orid"
              ? "border-sky-200/80 bg-gradient-to-br from-sky-50/90 to-white"
              : "border-amber-200/80 bg-gradient-to-br from-amber-50/90 to-white",
          ].join(" ")}
        >
          <div className="mb-2 text-[11px] font-bold text-amber-900 md:text-xs">{current.badge}</div>
          <div className="flex items-start gap-2">
            <PersimmonBullet size={18} className="mt-0.5 shrink-0" />
            <p className="text-sm leading-relaxed text-amber-950 md:text-[15px] md:leading-relaxed">
              {current.text}
            </p>
          </div>
          <p className="mt-3 text-[10px] text-amber-900/50 md:text-[11px]">
            {atEnd ? "看完提示了嗎？可以回到左邊開始寫作喔！" : "想好了就按「下一步」"}
          </p>
        </div>
      </div>

      <div className="flex shrink-0 gap-2 border-t border-amber-100 bg-white/80 px-2 py-2 md:px-3">
        <button
          type="button"
          onClick={goPrev}
          disabled={atStart}
          className="flex min-h-[44px] flex-1 items-center justify-center gap-1 rounded-xl border-2 border-amber-200 bg-[#faf5eb] text-xs font-semibold text-amber-900 transition hover:bg-amber-50 disabled:cursor-not-allowed disabled:opacity-40 md:text-sm"
        >
          <ChevronLeft className="h-4 w-4 shrink-0" aria-hidden />
          上一步
        </button>
        <button
          type="button"
          onClick={goNext}
          disabled={atEnd}
          className="flex min-h-[44px] flex-[1.15] items-center justify-center gap-1 rounded-xl bg-gradient-to-r from-amber-600 to-orange-700 text-xs font-semibold text-white shadow-sm transition hover:from-amber-500 hover:to-orange-600 disabled:cursor-not-allowed disabled:opacity-40 md:text-sm"
        >
          下一步
          <ChevronRight className="h-4 w-4 shrink-0" aria-hidden />
        </button>
      </div>
    </div>
  );
}
