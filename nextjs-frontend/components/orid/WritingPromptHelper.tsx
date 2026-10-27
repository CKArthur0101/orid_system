"use client";

import { useEffect, useRef, useState, type PointerEvent } from "react";
import Image from "next/image";
import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { PersimmonBullet } from "./PersimmonBullet";
import {
  controlGuideBookIdFromWeek,
  getControlGuidePages,
  getSynthesisGuidePages,
  type ControlGuideBookId,
  type ControlGuidePage,
} from "@/lib/orid/control-guide-pages";

type StageKey = "O" | "R" | "I" | "D";
type HelperMode = "prompt" | "sentence" | "check";
type TouchDragState = { text: string; x: number; y: number };

const INSERT_LABEL_PREFIX = /^(先寫開頭|再接感受|再寫體會|最後寫行動)\s*[：:]\s*/;

interface WritingPromptHelperProps {
  focusStage: StageKey;
  onPromptViewed?: () => void;
  onInsertText?: (text: string) => void;
  /** Week-2 synthesis mode for control group: show synthesis-specific prompts */
  synthesisMode?: boolean;
  /** Personalized opening reference (control group synthesis tab) */
  openingText?: string;
  /** Book pack key for parameterized control guides (book2/3 fall back to generic). */
  bookId?: ControlGuideBookId | string | null;
  /** Academic week 1–7; used when bookId is omitted. */
  week?: number;
  /** System ticks after 檢查. Null before the student presses the button. */
  systemChecks?: { label: string; passed: boolean }[] | null;
  /** Bumps when a new check result arrives so this panel opens on 自我檢查. */
  revealCheckToken?: number;
}

const STAGE_CHECKLIST: Record<StageKey, string[]> = {
  O: ["我有寫出故事裡的人物和事情，也能看出大致發展"],
  R: ["我有寫出感受，也用故事裡的事說明原因"],
  I: ["我有寫出學到的道理，也用故事說明"],
  D: ["我有寫出自己做得到的行動"],
};

const SYNTHESIS_CHECKLIST = [
  "我有把故事、感受、體會和行動寫進這篇",
  "我有把前後句接起來",
  "我有用故事說明自己的感受或學習原因",
  "我有寫出自己做得到、而且呼應故事的行動",
];

const TOPIC_TITLES: Record<StageKey, string[]> = {
  O: ["人物和事情", "故事順序", "印象深刻", "重要情節"],
  R: ["我的感覺", "感覺原因", "角色想法", "如果是我"],
  I: ["學到什麼", "故事改變", "生活連結", "自己的想法"],
  D: ["遇到什麼", "對誰行動", "怎麼做", "一件小事"],
};

const SYNTHESIS_TOPIC_TITLES = ["故事事件", "感受原因", "學到什麼", "以後行動"];

function textForWritingBox(text: string): string {
  return text.replace(INSERT_LABEL_PREFIX, "").trim();
}

export function WritingPromptHelper({
  focusStage,
  onPromptViewed,
  onInsertText,
  synthesisMode,
  openingText,
  bookId,
  week,
  systemChecks,
  revealCheckToken = 0,
}: WritingPromptHelperProps) {
  const resolvedBookId =
    bookId ?? (typeof week === "number" ? controlGuideBookIdFromWeek(week) : "book1");
  const pages: ControlGuidePage[] = synthesisMode
    ? getSynthesisGuidePages(resolvedBookId)
    : getControlGuidePages(focusStage, resolvedBookId);
  const [mode, setMode] = useState<HelperMode>("prompt");
  const [pageIndex, setPageIndex] = useState(0);
  const [insertMsg, setInsertMsg] = useState<string | null>(null);
  const [touchDrag, setTouchDrag] = useState<TouchDragState | null>(null);
  const suppressClickRef = useRef(false);
  const touchDragRef = useRef<{
    text: string;
    startX: number;
    startY: number;
    pointerId: number;
    dragging: boolean;
  } | null>(null);

  const sentencePages = pages.filter((page) => page.track === "orid");
  const promptPages = pages.filter((page) => page.track !== "orid");
  const promptTopics = promptPages.length > 0 ? promptPages : pages;
  const activePages = mode === "sentence" ? sentencePages : promptTopics;
  const checklistItems = synthesisMode ? SYNTHESIS_CHECKLIST : STAGE_CHECKLIST[focusStage];
  const shownChecks =
    systemChecks && systemChecks.length > 0
      ? systemChecks
      : checklistItems.map((label) => ({ label, passed: false }));
  const topicTitles = synthesisMode ? SYNTHESIS_TOPIC_TITLES : TOPIC_TITLES[focusStage];
  const _bookIdKey = String(resolvedBookId).trim().toLowerCase();
  const helperImageSrc =
    _bookIdKey === "book1" || _bookIdKey === "1"
      ? "/images/orid/week1/week1-grandpa-thinking-clean.png"
      : _bookIdKey === "book2" || _bookIdKey === "2"
        ? "/images/orid/week3/week3-zhu-mama-helper.png"
        : _bookIdKey === "book3" || _bookIdKey === "3"
          ? "/images/orid/week5/week5-lion-helper.png"
          : "/images/orid/system/system-thinking.png";

  useEffect(() => {
    setMode("prompt");
    setPageIndex(0);
    setInsertMsg(null);
  }, [focusStage, synthesisMode, resolvedBookId]);

  useEffect(() => {
    if (revealCheckToken > 0) setMode("check");
  }, [revealCheckToken]);

  const current = activePages[pageIndex] ?? activePages[0] ?? pages[0];
  const total = mode === "check" ? shownChecks.length : activePages.length;
  const atStart = pageIndex <= 0;
  const atEnd = pageIndex >= total - 1;

  function notePromptOpened() {
    onPromptViewed?.();
  }

  function goPrev() {
    if (mode === "check") return;
    if (atStart) return;
    setPageIndex((i) => i - 1);
  }

  function goNext() {
    if (mode === "check") return;
    if (atEnd) return;
    setPageIndex((i) => i + 1);
  }

  function switchMode(nextMode: HelperMode) {
    setMode(nextMode);
    setPageIndex(0);
    setInsertMsg(null);
    if (nextMode !== "check") notePromptOpened();
  }

  function selectTopic(index: number) {
    setPageIndex(index);
    setInsertMsg(null);
    notePromptOpened();
  }

  function sentenceOptions(): string[] {
    if (mode !== "sentence" || sentencePages.length === 0) return [];
    const matched = sentencePages[pageIndex % sentencePages.length];
    return matched ? [matched.text, ...(matched.supportingTexts ?? [])] : [];
  }

  function insertText(text: string) {
    onInsertText?.(textForWritingBox(text));
    setInsertMsg("已放進寫作格");
    window.setTimeout(() => setInsertMsg(null), 1600);
  }

  function startTouchDrag(event: PointerEvent<HTMLButtonElement>, text: string) {
    if (event.pointerType === "mouse") return;
    const insertText = textForWritingBox(text);
    touchDragRef.current = {
      text: insertText,
      startX: event.clientX,
      startY: event.clientY,
      pointerId: event.pointerId,
      dragging: false,
    };
    event.currentTarget.setPointerCapture?.(event.pointerId);
  }

  function moveTouchDrag(event: PointerEvent<HTMLButtonElement>) {
    const drag = touchDragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;

    const moved = Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY);
    if (!drag.dragging && moved < 10) return;

    drag.dragging = true;
    event.preventDefault();
    setTouchDrag({ text: drag.text, x: event.clientX, y: event.clientY });
  }

  function endTouchDrag(event: PointerEvent<HTMLButtonElement>) {
    const drag = touchDragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;

    touchDragRef.current = null;
    setTouchDrag(null);

    if (!drag.dragging) return;
    event.preventDefault();
    suppressClickRef.current = true;
    window.setTimeout(() => {
      suppressClickRef.current = false;
    }, 0);
    const target = document.elementFromPoint(event.clientX, event.clientY);
    const textarea = target instanceof Element ? target.closest("textarea") : null;
    if (textarea instanceof HTMLTextAreaElement) {
      insertText(drag.text);
    }
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
              {mode === "sentence"
                ? "選一個固定句型，可拖到寫作格"
                : mode === "check"
                  ? "按檢查後，系統會幫你打勾"
                  : "先讀問題，再想清楚要寫什麼"}
            </div>
          </div>
        </div>
        <div className="mt-2 flex items-center justify-between gap-2">
          <span className="shrink-0 text-[10px] font-semibold text-amber-800/80 md:text-xs">
            {mode === "check" ? `自我檢查／共 ${total} 項` : `第 ${pageIndex + 1} 張／共 ${total} 張`}
          </span>
          <div className="flex min-w-0 flex-1 justify-end gap-1" aria-hidden>
            {Array.from({ length: total }).map((_, i) => (
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
        <div className="mt-2 grid grid-cols-3 gap-1.5">
          {[
            ["prompt", "提示卡"],
            ["sentence", "句型卡"],
            ["check", "自我檢查"],
          ].map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => switchMode(key as HelperMode)}
              aria-pressed={mode === key}
              className={[
                "min-h-[36px] rounded-full border px-2 text-[11px] font-semibold transition md:text-xs",
                mode === key
                  ? "border-amber-700 bg-amber-800 text-white"
                  : "border-amber-200 bg-white/80 text-amber-900 hover:bg-amber-50",
              ].join(" ")}
            >
              {label}
            </button>
          ))}
        </div>
        {mode !== "check" ? (
          <div className="mt-2 flex gap-1.5 overflow-x-auto pb-0.5">
            {activePages.map((_, i) => (
              <button
                key={`topic-${i}`}
                type="button"
                onClick={() => selectTopic(i)}
                aria-pressed={pageIndex === i}
                className={[
                  "shrink-0 rounded-full border px-2.5 py-1 text-[10px] font-semibold transition md:text-[11px]",
                  pageIndex === i
                    ? "border-sky-500 bg-sky-100 text-sky-950"
                    : "border-amber-200 bg-white/75 text-amber-900 hover:bg-amber-50",
                ].join(" ")}
              >
                {topicTitles[i] ?? `主題 ${i + 1}`}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden p-2 md:p-3">
        {synthesisMode && openingText && mode === "prompt" && pageIndex === 0 ? (
          <div className="kid-bubble-ai mb-2 shrink-0 border border-amber-100/80 bg-amber-50/40 text-xs leading-relaxed md:text-sm">
            <div className="whitespace-pre-wrap">{openingText}</div>
          </div>
        ) : null}

        <div
          className={[
            "relative flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border-2 p-3 shadow-sm md:p-4",
            current.track === "orid"
              ? "border-sky-200/80 bg-gradient-to-br from-sky-50/90 to-white"
              : "border-amber-200/80 bg-gradient-to-br from-amber-50/90 to-white",
          ].join(" ")}
        >
          {mode === "check" ? (
            <div className="flex min-h-0 flex-1 flex-col justify-center gap-2">
              {systemChecks && systemChecks.length > 0 && systemChecks.every((item) => item.passed) ? (
                <div className="rounded-xl bg-emerald-600 px-3 py-2 text-center text-sm font-bold text-white">
                  {synthesisMode ? "這篇可以了" : "這段可以了"}
                </div>
              ) : systemChecks && systemChecks.length > 0 ? (
                <div className="rounded-xl bg-amber-700 px-3 py-2 text-center text-sm font-bold text-white">
                  {synthesisMode ? "這篇還沒通過" : "這段還沒通過"}
                </div>
              ) : (
                <div className="mb-1 text-[11px] font-bold text-amber-900 md:text-xs">
                  按「檢查」後，系統會依你寫的內容打勾
                </div>
              )}
              {shownChecks.map((item, idx) => (
                <label
                  key={`${item.label}-${idx}`}
                  className="flex items-start gap-2 rounded-xl border border-emerald-100 bg-emerald-50/70 px-2.5 py-2 text-xs leading-relaxed text-amber-950 md:text-sm"
                >
                  <input
                    type="checkbox"
                    className="mt-1 h-4 w-4 shrink-0 accent-emerald-600"
                    checked={item.passed}
                    readOnly
                    disabled
                  />
                  <span>{item.label}</span>
                </label>
              ))}
              <div className="mt-1 flex justify-end">
                <Image
                  src={helperImageSrc}
                  alt=""
                  width={64}
                  height={64}
                  className="h-12 w-12 object-contain opacity-95 md:h-14 md:w-14"
                />
              </div>
            </div>
          ) : (
            <div className="flex min-h-0 flex-1 flex-col justify-start gap-3 overflow-y-auto pr-0.5">
              <div className="mb-2 text-[11px] font-bold text-amber-900 md:text-xs">
                {mode === "sentence"
                  ? `✏️ 固定句型：${topicTitles[pageIndex] ?? current.badge}`
                  : `想一想：${topicTitles[pageIndex] ?? current.badge}`}
              </div>
              <div className="flex items-start gap-2 rounded-2xl border border-sky-200 bg-sky-50/90 p-3">
                <PersimmonBullet week={week} size={18} className="mt-0.5 shrink-0" />
                <p className="text-sm leading-relaxed text-amber-950 md:text-[15px] md:leading-relaxed">
                  {mode === "sentence" ? "選一個適合的句型，填入自己的故事和想法。" : current.text}
                </p>
              </div>
              {mode === "prompt" ? (
                <div className="space-y-2">
                  <div className="text-[11px] font-bold text-amber-900 md:text-xs">再想一想</div>
                  {(current.supportingTexts ?? []).map((text, idx) => (
                    <div
                      key={`${text}-${idx}`}
                      className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50/75 px-3 py-2.5"
                    >
                      <span className="mt-0.5 shrink-0 text-xs font-bold text-amber-600" aria-hidden>
                        {idx + 1}
                      </span>
                      <p className="text-xs leading-relaxed text-amber-950 md:text-sm">{text}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="text-[11px] font-bold text-amber-900 md:text-xs">
                    選一個句型拖到寫作格
                  </div>
                  {sentenceOptions().map((text, idx) => (
                    <button
                      key={`${text}-${idx}`}
                      type="button"
                      draggable
                      title="拖到寫作格，或按加號加入"
                      onDragStart={(event) => {
                        event.dataTransfer.setData("text/plain", textForWritingBox(text));
                      }}
                      onPointerDown={(event) => startTouchDrag(event, text)}
                      onPointerMove={moveTouchDrag}
                      onPointerUp={endTouchDrag}
                      onPointerCancel={() => {
                        touchDragRef.current = null;
                        setTouchDrag(null);
                      }}
                      onClick={(event) => {
                        if (suppressClickRef.current) {
                          event.preventDefault();
                          return;
                        }
                        insertText(text);
                      }}
                      className="flex w-full cursor-grab touch-none items-start gap-2 rounded-xl border border-amber-200 bg-amber-50/90 px-3 py-2 text-left text-sm font-semibold leading-relaxed text-amber-950 transition hover:bg-amber-100 active:cursor-grabbing"
                    >
                      <PersimmonBullet week={week} size={16} className="mt-0.5 shrink-0" />
                      <span className="min-w-0 flex-1">{text}</span>
                      <Plus className="mt-0.5 h-4 w-4 shrink-0 text-amber-800" aria-hidden />
                    </button>
                  ))}
                  {insertMsg ? <div className="text-xs font-semibold text-emerald-700">{insertMsg}</div> : null}
                </div>
              )}
              <p className="mt-3 text-[10px] text-amber-900/50 md:text-[11px]">
                {atEnd
                  ? synthesisMode
                    ? "看完了嗎？可以回到中間大框寫，或切到自我檢查。"
                    : "看完了嗎？可以回到左邊寫，或切到自我檢查。"
                  : mode === "sentence"
                    ? "想換一句固定句型，就按「下一張」"
                    : "想好了就按「下一張」"}
              </p>
              <div className="mt-auto flex justify-end pt-2">
                <Image
                  src={helperImageSrc}
                  alt=""
                  width={72}
                  height={72}
                  className="h-14 w-14 object-contain opacity-95 md:h-16 md:w-16"
                />
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="flex shrink-0 gap-2 border-t border-amber-100 bg-white/80 px-2 py-2 md:px-3">
        <button
          type="button"
          onClick={goPrev}
          disabled={mode === "check" || atStart}
          className="kid-btn-3d-secondary min-h-[44px] flex-1 !rounded-xl !text-xs md:!text-sm"
        >
          <ChevronLeft className="h-4 w-4 shrink-0" aria-hidden />
          上一張
        </button>
        <button
          type="button"
          onClick={goNext}
          disabled={mode === "check" || atEnd}
          className="kid-btn-3d-primary min-h-[44px] flex-[1.15] !rounded-xl !text-xs md:!text-sm"
        >
          下一張
          <ChevronRight className="h-4 w-4 shrink-0" aria-hidden />
        </button>
      </div>
      {touchDrag ? (
        <div
          className="pointer-events-none fixed z-[300] max-w-[18rem] rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 text-xs font-bold leading-relaxed text-amber-950 shadow-xl"
          style={{ left: touchDrag.x + 12, top: touchDrag.y + 12 }}
          aria-hidden
        >
          {touchDrag.text}
        </div>
      ) : null}
    </div>
  );
}
