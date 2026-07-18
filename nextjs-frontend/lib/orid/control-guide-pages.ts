type StageKey = "O" | "R" | "I" | "D";

export type ControlGuidePage = {
  /** orid = 寫作句型／故事觀察；sel = 心情／想法／行動引導（不對學生顯示 SEL 術語） */
  track: "orid" | "sel";
  badge: string;
  text: string;
};

const ORID_PROMPTS: Record<StageKey, string[]> = {
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

/** O 段以故事觀察提問為主（無 SEL rubric）；R/I/D 用 rubric 的 student_prompts */
const SEL_PROMPTS: Record<StageKey, string[]> = {
  O: [
    "故事中哪一個情節讓你印象最深？",
    "主角遇到了什麼問題？",
    "故事裡發生了哪些重要的事情？",
    "故事一開始，發生了什麼事？",
  ],
  R: [
    "故事中哪一個地方讓你有這種感覺？",
    "你的感覺可以再說得更清楚一點嗎？",
    "你覺得阿松爺爺當時可能在想什麼？",
    "如果你是故事裡的人，你可能會有什麼感覺？",
  ],
  I: [
    "這個故事想讓我們學到什麼？",
    "從阿松爺爺的改變，你覺得分享帶來什麼不同？",
    "阿松爺爺為什麼會有這樣的改變？",
    "哎唷奶奶的做法讓故事有什麼不一樣？",
  ],
  D: [
    "如果你遇到類似情況，你可以在什麼時候、對誰、怎麼做？",
    "這個行動會對你或別人有什麼幫助？",
    "看完這個故事，你想在生活中改變什麼？",
    "你可以在什麼時候、對誰做出類似的行動？",
  ],
};

const TRACK_BADGE: Record<"orid" | "sel", Record<StageKey, string>> = {
  orid: {
    O: "✏️ 觀察句型",
    R: "✏️ 感受句型",
    I: "✏️ 意義句型",
    D: "✏️ 行動句型",
  },
  sel: {
    O: "📖 故事觀察",
    R: "💛 感受想一想",
    I: "🌱 啟發想一想",
    D: "🤝 行動想一想",
  },
};

function interleavePages(orid: string[], sel: string[], stage: StageKey): ControlGuidePage[] {
  const count = Math.max(orid.length, sel.length);
  const pages: ControlGuidePage[] = [];
  for (let i = 0; i < count; i++) {
    if (i < orid.length) {
      pages.push({
        track: "orid",
        badge: TRACK_BADGE.orid[stage],
        text: orid[i],
      });
    }
    if (i < sel.length) {
      pages.push({
        track: "sel",
        badge: TRACK_BADGE.sel[stage],
        text: sel[i],
      });
    }
  }
  return pages;
}

export function getControlGuidePages(stage: StageKey): ControlGuidePage[] {
  return interleavePages(ORID_PROMPTS[stage], SEL_PROMPTS[stage], stage);
}

const SYNTHESIS_ORID = [
  "故事裡讓我印象最深的是……",
  "看到這件事時，我覺得……，因為……",
  "這讓我想到……",
  "我從這個故事學到……",
  "以後如果我遇到類似的情況，我會……",
];

const SYNTHESIS_SEL = [
  "你上週的 O 有提到哪個重要情節？可以用那個當開頭。",
  "你上週的 R 寫了什麼感受？可以用連接詞接到感受那一句。",
  "你上週的 I 有沒有體會或想法？可以寫「這讓我想到……」。",
  "你上週的 D 有沒有說要怎麼做？記得在結尾補上具體的行動。",
  "整合時，記得把「觀察 → 感受 → 想法 → 行動」接起來。",
];

export function getSynthesisGuidePages(): ControlGuidePage[] {
  return interleavePages(SYNTHESIS_ORID, SYNTHESIS_SEL, "I").map((page) =>
    page.track === "orid"
      ? { ...page, badge: "✏️ 整合句型" }
      : { ...page, badge: "📖 上週回顧" },
  );
}
