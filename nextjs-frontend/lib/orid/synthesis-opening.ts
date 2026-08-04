type StageKey = "O" | "R" | "I" | "D";

type WeekStages = {
  stages: Record<StageKey, { d1: string; d2: string }>;
};

export type SynthesisChecklist = {
  story: boolean;
  feeling: boolean;
  insight: boolean;
  action: boolean;
};

export const SYNTHESIS_CHECKLIST_LABELS: {
  key: keyof SynthesisChecklist;
  label: string;
}[] = [
  { key: "story", label: "有故事裡的事" },
  { key: "feeling", label: "有感受＋原因" },
  { key: "insight", label: "有學到／想到" },
  { key: "action", label: "有以後怎麼做" },
];

/**
 * Short opening for the right-hand synthesis chat.
 * Must keep prefix 「歡迎來到第 」 for persisted-message detection.
 *
 * Keeps structure hints only — no pasting last week's full O/R/I/D
 * (those stay on the left panel / 複製 buttons).
 */
export function buildSynthesisOpeningMessage(
  _priorWeek: WeekStages | null,
  bookTitle?: string | null,
  evenWeekNum: number = 2,
): string {
  const book = bookTitle?.trim() ? `《${bookTitle.trim()}》` : "這本書";
  const priorWeekNum = evenWeekNum - 1;
  return [
    `歡迎來到第 ${evenWeekNum} 週「整合寫作」！`,
    `這週把第 ${priorWeekNum} 週的四格，收成一篇跟 ${book} 有關的短文。`,
    "",
    "可以照這個順序寫：",
    "1. 故事裡的事　2. 感受＋原因　3. 學到什麼　4. 以後怎麼做",
    "",
    "左邊可看／複製上週原文。寫好後按「取得整合回饋」，我一次只幫你改一個重點。",
  ].join("\n");
}

/** Soft heuristics for optional checklist UI (not a hard pass bar). */
export function detectSynthesisDraftChecklist(draft: string): SynthesisChecklist {
  const t = (draft || "").replace(/\s+/g, "");
  return {
    story:
      /故事|阿松|爺爺|奶奶|柿子|開頭|一開始|後來|最後|藏|倉庫|大口|獨占|自己吃|砍|種子/.test(
        t,
      ) || /印象最深|發生了/.test(t),
    feeling: /覺得|心情|因為|小氣|生氣|難過|開心|糟|討厭|喜歡|故意/.test(t),
    insight: /學到|想到|明白|道理|提醒|原來|啟發|體悟/.test(t),
    action: /以後|我會|下次|如果遇到|打算|先/.test(t),
  };
}

export function synthesisChecklistDoneCount(c: SynthesisChecklist): number {
  return SYNTHESIS_CHECKLIST_LABELS.filter(({ key }) => c[key]).length;
}
