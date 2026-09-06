type StageKey = "O" | "R" | "I" | "D";

export type ControlGuidePage = {
  /** orid = fixed sentence frames; sel = fixed questions that help students think. */
  track: "orid" | "sel";
  badge: string;
  text: string;
  /** Two fixed follow-ups or alternative frames shown with the main item. */
  supportingTexts?: string[];
};

/** Book packs for control guides. book2/book3 TBD -> generic fallback. */
export type ControlGuideBookId = "book1" | "book2" | "book3" | "generic";

const ORID_SENTENCE_GROUPS: Record<StageKey, string[][]> = {
  O: [
    ["故事裡，＿＿做了＿＿。", "故事中有＿＿，他做了＿＿。", "＿＿看到＿＿，所以＿＿。"],
    ["一開始＿＿，接著＿＿。", "先發生＿＿，後來＿＿。", "故事的順序是＿＿，然後＿＿。"],
    ["我印象最深的是＿＿。", "故事中，我最記得＿＿。", "＿＿這一幕讓我印象很深。"],
    ["故事裡重要的一件事是＿＿。", "故事發生改變，是因為＿＿。", "這個情節很重要，因為＿＿。"],
  ],
  R: [
    ["我覺得＿＿。", "看到＿＿時，我感到＿＿。", "這一幕讓我的心情是＿＿。"],
    ["我覺得＿＿，因為＿＿。", "我會有這種感覺，是因為＿＿。", "＿＿讓我感到＿＿，因為＿＿。"],
    ["我想＿＿可能覺得＿＿。", "故事裡的＿＿可能在想＿＿。", "從＿＿的做法，我猜他覺得＿＿。"],
    ["如果我是＿＿，我會覺得＿＿。", "如果這件事發生在我身上，我可能會＿＿。", "換成是我，我的心情會是＿＿。"],
  ],
  I: [
    ["這個故事讓我學到＿＿。", "我從＿＿身上學到＿＿。", "讀完故事，我明白＿＿。"],
    ["故事裡的改變讓我發現＿＿。", "原來＿＿會讓事情變得＿＿。", "從一開始到最後，我看見＿＿。"],
    ["這讓我想到＿＿。", "我也曾經在＿＿時遇過類似的事。", "這件事和我的生活一樣，都＿＿。"],
    ["我認為＿＿，因為＿＿。", "我最同意＿＿的做法，因為＿＿。", "如果可以選，我會＿＿。"],
  ],
  D: [
    ["以後如果遇到＿＿，我會＿＿。", "下次碰到＿＿，我會先＿＿。", "如果再發生類似的事，我會＿＿。"],
    ["我會對＿＿做＿＿。", "當＿＿需要幫忙時，我會＿＿。", "我想和＿＿一起＿＿。"],
    ["我會先＿＿，再＿＿。", "我會用＿＿的方法來＿＿。", "遇到問題時，我會試著＿＿。"],
    ["我可以先做的一件小事是＿＿。", "今天我可以從＿＿開始。", "我準備在＿＿的時候做＿＿。"],
  ],
};

/** Generic story questions (no book-specific character names). */
const THINKING_GROUPS_GENERIC: Record<StageKey, string[][]> = {
  O: [
    ["故事裡有哪些人物？他們做了什麼？", "哪一個人物最重要？", "他做了哪一件事？"],
    ["故事先發生什麼，後來又發生什麼？", "事情是怎麼開始的？", "接著發生了什麼？"],
    ["故事中哪一個情節讓你印象最深？", "你最記得哪一幕？", "那一幕發生了什麼？"],
    ["哪一件事讓故事開始改變？", "主角遇到了什麼問題？", "這件事帶來什麼變化？"],
  ],
  R: [
    ["讀到這一段，你有什麼感覺？", "你的心情比較像開心、難過，還是擔心？", "哪一幕讓你有這種感覺？"],
    ["故事中哪一個地方讓你有這種感覺？", "是誰的哪個做法影響了你？", "為什麼這件事會讓你這樣想？"],
    ["你覺得故事裡的人當時可能在想什麼？", "他為什麼會有這種心情？", "你從他的哪個做法看出來？"],
    ["如果你是故事裡的人，你可能會有什麼感覺？", "你會擔心什麼？", "你最希望有人怎麼幫你？"],
  ],
  I: [
    ["這個故事想讓我們學到什麼？", "哪一個人物讓你學到這件事？", "這個想法為什麼重要？"],
    ["從主角的改變，你發現了什麼？", "他一開始和最後有什麼不同？", "這個改變帶來什麼結果？"],
    ["故事讓你想到自己的哪一次經驗？", "你曾在什麼時候遇過類似的事？", "你當時怎麼做？"],
    ["你同意故事人物的做法嗎？", "你為什麼這樣想？", "你覺得還能怎麼做？"],
  ],
  D: [
    ["以後遇到類似情況，你會怎麼做？", "你會在什麼時候這樣做？", "你希望事情有什麼改變？"],
    ["你想把行動用在誰身上？", "對方可能需要什麼幫助？", "這個行動會帶來什麼幫助？"],
    ["你準備用什麼方法做到？", "第一步可以先做什麼？", "遇到困難時，你可以找誰幫忙？"],
    ["今天就能開始的小事是什麼？", "你可以在哪裡做這件事？", "做完後，你想看看有什麼改變？"],
  ],
};

/** Book 1 character-grounded questions; writing frames remain book-neutral. */
const THINKING_GROUPS_BOOK1: Record<StageKey, string[][]> = {
  O: THINKING_GROUPS_GENERIC.O,
  R: [
    ...THINKING_GROUPS_GENERIC.R.slice(0, 2),
    ["你覺得阿松爺爺當時可能在想什麼？", "他為什麼會有這種心情？", "你從他的哪個做法看出來？"],
    ["如果你是阿松爺爺，你可能會有什麼感覺？", "你會擔心什麼？", "你最希望有人怎麼幫你？"],
  ],
  I: [
    THINKING_GROUPS_GENERIC.I[0],
    [
      "從阿松爺爺的改變，你覺得分享帶來什麼不同？",
      "他一開始和最後有什麼不同？",
      "這個改變帶來什麼結果？",
    ],
    THINKING_GROUPS_GENERIC.I[2],
    ["哎唷奶奶的做法讓故事有什麼不一樣？", "你同意她的做法嗎？", "你覺得還能怎麼做？"],
  ],
  D: THINKING_GROUPS_GENERIC.D,
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

function pageFromGroup(
  track: "orid" | "sel",
  badge: string,
  group: string[],
): ControlGuidePage {
  const [text, ...supportingTexts] = group;
  return { track, badge, text, supportingTexts };
}

function interleavePages(orid: string[][], sel: string[][], stage: StageKey): ControlGuidePage[] {
  const count = Math.max(orid.length, sel.length);
  const pages: ControlGuidePage[] = [];

  for (let i = 0; i < count; i++) {
    if (orid[i]) pages.push(pageFromGroup("orid", TRACK_BADGE.orid[stage], orid[i]));
    if (sel[i]) pages.push(pageFromGroup("sel", TRACK_BADGE.sel[stage], sel[i]));
  }

  return pages;
}

/** Weeks 1-2 -> book1; 3-4 -> book2; 5-6 -> book3. */
export function controlGuideBookIdFromWeek(week: number): ControlGuideBookId {
  if (!Number.isFinite(week) || week < 1) return "generic";
  const unit = Math.ceil(week / 2);
  if (unit === 1) return "book1";
  if (unit === 2) return "book2";
  if (unit === 3) return "book3";
  return "generic";
}

/** Book 2 character-grounded questions for 《朱家故事》. */
const THINKING_GROUPS_BOOK2: Record<StageKey, string[][]> = {
  O: [
    ["故事一開始，朱先生、小吉和小利對朱太太說了什麼？", "他們說話的語氣是怎樣的？", "朱太太聽到後做了什麼？"],
    ["朱太太每天出門上班前，做了哪些家事？", "可以先找早上那一段的內容。", "請按照故事順序回想，不要加入自己的感覺。"],
    ["朱太太不在家的幾天，朱先生和孩子們遇到了哪些困難？", "可以想想他們做飯和整理家裡時發生了什麼。", "注意故事說家裡後來變成什麼樣子。"],
    ["朱太太回來後，朱先生、小吉和小利做了哪些改變？", "可以找出他們各自幫忙做了哪些事。", "注意故事最後大家一起做家事時的情況。"],
  ],
  R: [
    ["看到朱太太每天做這麼多事，你有什麼感覺？", "可以想想她早上、傍晚和晚上都在忙什麼。", "你的感覺可以是心疼、生氣、驚訝，也可以是其他感覺。"],
    ["看到朱先生和孩子們一直催朱太太，你有什麼感覺？", "可以回想他們早上和傍晚說了哪些話。", "想一想如果你是朱太太，聽到這些話可能會怎麼想。"],
    ["看到朱太太留下「你們是豬！」這張紙條時，你有什麼感覺？", "可以想想朱太太為什麼會這樣做。", "也可以想想朱先生和孩子們看到紙條時可能有什麼心情。"],
    ["看到朱家最後一起做家事，你有什麼感覺？", "可以想想故事前面和後面有什麼不同。", "可以寫出你覺得開心、安心、溫暖或其他感覺的原因。"],
  ],
  I: [
    ["你覺得《朱家故事》想讓我們思考家事應該怎麼分擔？", "可以想想朱太太一開始做了多少事情。", "也可以想想大家後來一起動手後發生了什麼改變。"],
    ["你覺得朱太太為什麼要離開家？", "可以回想朱先生和孩子們平常怎麼對她說話。", "不要只看紙條，也可以想想前面累積了哪些事情。"],
    ["朱先生、小吉和小利後來可能明白了什麼？", "可以從他們自己做飯、找東西吃、請朱太太留下來這些地方想。", "也可以想想他們後來為什麼願意幫忙。"],
    ["這個故事讓你想到，家人之間可以怎麼互相尊重？", "可以想想說話的方式和分擔事情的方式。", "尊重不一定只是說謝謝，也可以表現在行動上。"],
  ],
  D: [
    ["看完《朱家故事》後，你在家裡可以主動做哪一件事？", "可以想想吃飯前後、整理房間或洗衣服時能做什麼。", "請寫你真的做得到的小行動。"],
    ["如果你需要家人幫忙，你可以怎麼說得更有禮貌？", "可以回想朱先生和孩子們一開始說話的方式。", "想一想怎樣說會讓對方比較舒服。"],
    ["如果你看到家人很忙或很累，你可以怎麼做？", "可以先觀察對方正在忙什麼。", "你可以寫出一句話或一個行動。"],
    ["你可以怎麼和家人一起分擔家裡的事情？", "可以想想故事最後大家一起做家事的畫面。", "也可以想想自己最適合負責哪一件小事。"],
  ],
};

function resolveThinkingGroups(
  bookId?: ControlGuideBookId | string | null,
): Record<StageKey, string[][]> {
  const key = String(bookId || "book1").trim().toLowerCase();
  if (key === "book1" || key === "1") return THINKING_GROUPS_BOOK1;
  if (key === "book2" || key === "2") return THINKING_GROUPS_BOOK2;
  // Book 3 uses generic fixed questions until its content is finalized.
  return THINKING_GROUPS_GENERIC;
}

export function getControlGuidePages(
  stage: StageKey,
  bookId?: ControlGuideBookId | string | null,
): ControlGuidePage[] {
  return interleavePages(ORID_SENTENCE_GROUPS[stage], resolveThinkingGroups(bookId)[stage], stage);
}

const SYNTHESIS_SENTENCE_GROUPS = [
  ["先寫開頭：故事裡讓我印象最深的是＿＿。", "故事裡，＿＿做了＿＿。", "一開始＿＿，後來＿＿。"],
  ["再接感受：看到這件事時，我覺得＿＿，因為＿＿。", "這一幕讓我感到＿＿，因為＿＿。", "如果我是＿＿，我可能會覺得＿＿。"],
  ["再寫體會：這讓我想到＿＿。", "這個故事讓我學到＿＿。", "我從＿＿身上明白＿＿。"],
  ["最後寫行動：以後遇到＿＿時，我會＿＿。", "下次碰到類似的事，我會先＿＿。", "我可以先做的一件小事是＿＿。"],
];

const SYNTHESIS_THINKING_GROUPS = [
  ["哪一件故事事件最適合當開頭？", "這件事是誰做的？", "事情先後是怎麼發生的？"],
  ["這件事帶給你什麼感覺？", "是哪個情節讓你有這種感覺？", "你為什麼會這樣想？"],
  ["這個故事讓你學到或想到什麼？", "故事人物的改變提醒你什麼？", "這和你的生活有什麼關係？"],
  ["以後遇到類似情況，你會怎麼做？", "你會在什麼時候、對誰這樣做？", "你準備先做哪一件小事？"],
];

export function getSynthesisGuidePages(
  _bookId?: ControlGuideBookId | string | null,
): ControlGuidePage[] {
  const pages: ControlGuidePage[] = [];
  for (let i = 0; i < SYNTHESIS_SENTENCE_GROUPS.length; i++) {
    pages.push(pageFromGroup("orid", "✏️ 一步一步寫", SYNTHESIS_SENTENCE_GROUPS[i]));
    pages.push(pageFromGroup("sel", "✓ 寫之前想一想", SYNTHESIS_THINKING_GROUPS[i]));
  }
  return pages;
}
