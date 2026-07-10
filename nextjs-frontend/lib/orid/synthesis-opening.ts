type StageKey = "O" | "R" | "I" | "D";

type WeekStages = {
  stages: Record<StageKey, { d1: string; d2: string }>;
};

const STAGE_HINTS: Record<
  StageKey,
  { label: string; empty: string; hasContent: (t: string) => string }
> = {
  O: {
    label: "O 觀察",
    empty: "你上週的 O 還可以再補充故事裡發生了什麼事，整合時記得在開頭帶出一件重要的事。",
    hasContent: (t) => {
      const snippet = t.length > 55 ? t.slice(0, 55) + "…" : t;
      return `你有寫到「${snippet}」——整合時可以從這裡帶出開頭。`;
    },
  },
  R: {
    label: "R 感受",
    empty: "你上週的 R 還不多，整合時可以補上「看到這件事時，我覺得……，因為……」。",
    hasContent: (t) => {
      const snippet = t.length > 45 ? t.slice(0, 45) + "…" : t;
      return `你有寫到感受「${snippet}」——可以接在故事事件後面。`;
    },
  },
  I: {
    label: "I 體悟",
    empty: "你上週的 I 還不多，整合時可以補上「這讓我想到……」或「我從這個故事學到……」。",
    hasContent: (t) => {
      const snippet = t.length > 45 ? t.slice(0, 45) + "…" : t;
      return `你有想到「${snippet}」——可以當文章的中段體會。`;
    },
  },
  D: {
    label: "D 行動",
    empty: "你上週的 D 還不多，整合時記得在結尾寫「以後如果我遇到類似的情況，我會……」。",
    hasContent: (t) => {
      const snippet = t.length > 45 ? t.slice(0, 45) + "…" : t;
      return `你有寫到「${snippet}」——可以放在文章結尾呼應。`;
    },
  },
};

const MIN_LEN = 12;

/**
 * Build the opening message for an even-week synthesis session.
 *
 * @param priorWeek  - The writing data from the preceding odd week (may be null).
 * @param bookTitle  - Optional book title to personalise the message.
 * @param evenWeekNum - The current even week number (defaults to 2 for backward compat).
 */
export function buildSynthesisOpeningMessage(
  priorWeek: WeekStages | null,
  bookTitle?: string | null,
  evenWeekNum: number = 2,
): string {
  const book = bookTitle?.trim() ? `《${bookTitle.trim()}》` : "這本書";
  const priorWeekNum = evenWeekNum - 1;
  const w = priorWeek ?? {
    stages: { O: { d1: "", d2: "" }, R: { d1: "", d2: "" }, I: { d1: "", d2: "" }, D: { d1: "", d2: "" } },
  };

  const stageLines = (["O", "R", "I", "D"] as StageKey[]).map((key) => {
    const text = String(w.stages[key]?.d1 ?? "").trim();
    const hint = STAGE_HINTS[key];
    const line = text.length >= MIN_LEN ? hint.hasContent(text) : hint.empty;
    return `・${hint.label}：${line}`;
  });

  return [
    `歡迎來到第 ${evenWeekNum} 週「整合寫作」！`,
    `這週請把第 ${priorWeekNum} 週的四段 ORID 收成一篇跟 ${book} 有關的完整反思短文。`,
    `左邊可以看你的上週原文；這裡依你的內容整理下筆參考（不是幫你寫好答案）：`,
    "",
    ...stageLines,
    "",
    "【可以這樣接起來寫】",
    "1. 開頭：「故事裡讓我印象最深的是……」",
    "2. 中間：「看到這件事時，我覺得……，因為……」",
    "3. 體會：「這讓我想到……」或「我從這個故事學到……」",
    "4. 結尾：「以後如果我遇到類似的情況，我會……」",
    "",
    "請在中間大框寫整合稿；寫好後按「取得整合回饋」，我會針對整篇文章給你三段建議。",
  ].join("\n");
}
