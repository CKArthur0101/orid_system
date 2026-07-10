"use client";

import { useState } from "react";
import { PersimmonBullet } from "./PersimmonBullet";

type StageKey = "O" | "R" | "I" | "D";

// Synthesis mode fixed prompts for control group (week 2)
const SYNTHESIS_PROMPTS: string[] = [
  "故事裡讓我印象最深的是……",
  "看到這件事時，我覺得……，因為……",
  "這讓我想到……",
  "我從這個故事學到……",
  "以後如果我遇到類似的情況，我會……",
];

const SYNTHESIS_QUESTIONS: string[] = [
  "你上週的 O 有提到哪個重要情節？可以用那個當開頭。",
  "你上週的 R 寫了什麼感受？可以用連接詞接到感受那一句。",
  "你上週的 I 有沒有體會或想法？可以寫「這讓我想到……」。",
  "你上週的 D 有沒有說要怎麼做？記得在結尾補上具體的行動。",
];

// Fixed sentence starters for each ORID stage
const FIXED_PROMPTS: Record<StageKey, string[]> = {
  O: [
    "故事中，______做了______。",
    "一開始______，後來______。",
    "我印象最深的是______。",
    "我在故事中看到……",
  ],
  R: [
    "我覺得……因為……",
    "我覺得______，因為______。",
    "看到______這一幕，我感到______。",
    "如果我是______，我可能會覺得______。",
  ],
  I: [
    "這讓我想到……",
    "這個故事讓我學到______。",
    "這件事提醒我要______，因為______。",
    "我發現自己很在乎______。",
  ],
  D: [
    "以後如果遇到類似情況，我會……",
    "以後如果我遇到______，我會______。",
    "下次當我想______的時候，我會先______。",
    "我可以做的一件小事是：______。",
  ],
};

// Fixed book content questions for each ORID stage
const BOOK_QUESTIONS: Record<StageKey, string[]> = {
  O: [
    "故事中哪一個情節讓你印象最深？",
    "主角遇到了什麼問題？",
    "故事裡發生了哪些重要的事情？",
  ],
  R: [
    "你覺得角色當時可能有什麼感受？",
    "這個故事讓你有什麼感覺，為什麼？",
    "哪一個場景讓你最有感觸？",
  ],
  I: [
    "這個故事讓你想到自己的什麼經驗？",
    "故事想讓我們學到什麼？",
    "這個故事帶給你什麼樣的啟發？",
  ],
  D: [
    "如果你是故事中的角色，你會怎麼做？",
    "看完這個故事，你想在生活中改變什麼？",
    "你可以在什麼時候、對誰做出類似的行動？",
  ],
};

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
  const [expanded, setExpanded] = useState(false);

  function handleViewPrompts() {
    setExpanded(true);
    onPromptViewed?.();
  }

  const prompts = synthesisMode ? SYNTHESIS_PROMPTS : (FIXED_PROMPTS[focusStage] ?? FIXED_PROMPTS.O);
  const questions = synthesisMode ? SYNTHESIS_QUESTIONS : (BOOK_QUESTIONS[focusStage] ?? BOOK_QUESTIONS.O);

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-[#fffcf7]">
      {/* Header */}
      <div className="shrink-0 border-b border-amber-100 px-3 py-3 sm:px-4">
        <div className="flex items-center gap-2">
          <span className="text-xl">🌰</span>
          <div>
            <div className="text-sm font-bold text-amber-950">
              {synthesisMode ? "整合寫作提示" : "寫作提示小幫手"}
            </div>
            <div className="text-[11px] text-amber-900/60">
              {synthesisMode
                ? "句型提示 + 上週內容提問，幫助你完成整合短文"
                : "固定提示句 + 書本問題，幫助你寫出更完整的反思"}
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {synthesisMode && openingText ? (
          <div className="kid-bubble-ai mb-3 border border-amber-100/80 bg-amber-50/40 text-sm leading-relaxed">
            <div className="whitespace-pre-wrap">{openingText}</div>
          </div>
        ) : null}
        {!expanded ? (
          <div className="flex flex-col items-center gap-3 py-4">
            <p className="text-center text-sm text-amber-900/70">
              需要一點靈感嗎？點下方按鈕看寫作提示！
            </p>
            <button
              type="button"
              onClick={handleViewPrompts}
              className="rounded-xl bg-amber-500 px-5 py-2.5 text-sm font-bold text-white shadow-sm hover:bg-amber-600 active:scale-95"
            >
              查看寫作提示
            </button>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {/* Sentence starters */}
            <div>
              <div className="mb-2 text-xs font-bold text-amber-900">
                {synthesisMode ? "✏️ 整合句型提示" : "✏️ 固定提示句"}
              </div>
              <div className="flex flex-col gap-1.5">
                {prompts.map((p) => (
                  <div key={p} className="flex items-start gap-1.5">
                    <PersimmonBullet size={14} className="mt-0.5 shrink-0" />
                    <span className="text-xs leading-relaxed text-amber-950/85">{p}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Book content questions */}
            <div>
              <div className="mb-2 text-xs font-bold text-amber-900">
                {synthesisMode ? "📖 上週 ORID 提問" : "📖 書本內文問題"}
              </div>
              <div className="flex flex-col gap-1.5">
                {questions.map((q) => (
                  <div key={q} className="flex items-start gap-1.5">
                    <PersimmonBullet size={14} className="mt-0.5 shrink-0" />
                    <span className="text-xs leading-relaxed text-amber-950/85">{q}</span>
                  </div>
                ))}
              </div>
            </div>

            <button
              type="button"
              onClick={() => setExpanded(false)}
              className="mt-1 text-xs text-amber-700 underline"
            >
              收起提示
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
