/**
 * Frontend badge rules — mirrors backend orid_badges.py.
 * Tooltip and modal copy is centralised here.
 */

export type BadgeId =
  | "badge_start"
  | "badge_30"
  | "badge_60"
  | "badge_90"
  | "badge_synthesis_content"
  | "badge_synthesis_coherence"
  | "badge_synthesis_reflection"
  | "badge_synthesis_action";

export type BadgeBookId = "book1" | "book2" | "book3";

export type OridStageKey = "O" | "R" | "I" | "D";

export interface BadgeConfig {
  id: BadgeId;
  name: string;
  /** Shown in tooltip when NOT yet earned */
  unlockHint: string;
  /** Shown in tooltip when ALREADY earned */
  earnedHint: string;
  /** Modal title on first earn */
  modalTitle: string;
  /** Modal body on first earn */
  modalText: string;
  /** Path to image asset (PNG) */
  svgPath: string;
}

export const BADGE_ORDER: BadgeId[] = [
  "badge_start",
  "badge_30",
  "badge_60",
  "badge_90",
  "badge_synthesis_content",
  "badge_synthesis_coherence",
  "badge_synthesis_reflection",
  "badge_synthesis_action",
];

export const ORID_BADGE_ORDER: BadgeId[] = [
  "badge_start",
  "badge_30",
  "badge_60",
  "badge_90",
];

export const SYNTHESIS_BADGE_ORDER: BadgeId[] = [
  "badge_synthesis_content",
  "badge_synthesis_coherence",
  "badge_synthesis_reflection",
  "badge_synthesis_action",
];

const BOOK1_BADGE_IMAGES: Record<BadgeId, string> = {
  badge_start: "/images/orid/badges/badge_persimmon_start.png",
  badge_30: "/images/orid/badges/badge_persimmon_bronze.png",
  badge_60: "/images/orid/badges/badge_persimmon_silver.png",
  badge_90: "/images/orid/badges/badge_persimmon_gold.png",
  badge_synthesis_content: "/images/orid/badges/badge_persimmon_start.png",
  badge_synthesis_coherence: "/images/orid/badges/badge_persimmon_bronze.png",
  badge_synthesis_reflection: "/images/orid/badges/badge_persimmon_silver.png",
  badge_synthesis_action: "/images/orid/badges/badge_persimmon_gold.png",
};

const BOOK2_BADGE_IMAGES: Record<BadgeId, string> = {
  badge_start: "/images/orid/badges/badge_pig_start.png",
  badge_30: "/images/orid/badges/badge_pig_bronze.png",
  badge_60: "/images/orid/badges/badge_pig_silver.png",
  badge_90: "/images/orid/badges/badge_pig_gold.png",
  badge_synthesis_content: "/images/orid/badges/badge_pig_start.png",
  badge_synthesis_coherence: "/images/orid/badges/badge_pig_bronze.png",
  badge_synthesis_reflection: "/images/orid/badges/badge_pig_silver.png",
  badge_synthesis_action: "/images/orid/badges/badge_pig_gold.png",
};

const BOOK3_BADGE_IMAGES: Record<BadgeId, string> = {
  badge_start: "/images/orid/badges/badge_lion_start.png",
  badge_30: "/images/orid/badges/badge_lion_bronze.png",
  badge_60: "/images/orid/badges/badge_lion_silver.png",
  badge_90: "/images/orid/badges/badge_lion_gold.png",
  badge_synthesis_content: "/images/orid/badges/badge_lion_start.png",
  badge_synthesis_coherence: "/images/orid/badges/badge_lion_bronze.png",
  badge_synthesis_reflection: "/images/orid/badges/badge_lion_silver.png",
  badge_synthesis_action: "/images/orid/badges/badge_lion_gold.png",
};

const BADGE_IMAGES_BY_BOOK: Record<BadgeBookId, Record<BadgeId, string>> = {
  book1: BOOK1_BADGE_IMAGES,
  book2: BOOK2_BADGE_IMAGES,
  book3: BOOK3_BADGE_IMAGES,
};

const BOOK2_BADGE_NAMES: Partial<Record<BadgeId, { name: string; modalTitle: string }>> = {
  badge_start: { name: "下筆豬頭章", modalTitle: "恭喜獲得下筆徽章！" },
  badge_30: { name: "豬頭銅徽章", modalTitle: "恭喜獲得豬頭銅徽章！" },
  badge_60: { name: "豬頭銀徽章", modalTitle: "恭喜獲得豬頭銀徽章！" },
  badge_90: { name: "豬頭金徽章", modalTitle: "恭喜獲得豬頭金徽章！" },
};

const BOOK3_BADGE_NAMES: Partial<Record<BadgeId, { name: string; modalTitle: string }>> = {
  badge_start: { name: "下筆獅子章", modalTitle: "恭喜獲得下筆徽章！" },
  badge_30: { name: "獅子銅徽章", modalTitle: "恭喜獲得獅子銅徽章！" },
  badge_60: { name: "獅子銀徽章", modalTitle: "恭喜獲得獅子銀徽章！" },
  badge_90: { name: "獅子金徽章", modalTitle: "恭喜獲得獅子金徽章！" },
};

export function resolveBadgeBookId(
  bookId?: string | null,
  week?: number | null,
): BadgeBookId {
  const key = String(bookId || "").trim().toLowerCase();
  if (key === "book1" || key === "1") return "book1";
  if (key === "book2" || key === "2") return "book2";
  if (key === "book3" || key === "3") return "book3";
  if (typeof week === "number" && Number.isFinite(week) && week >= 1) {
    const unit = Math.ceil(week / 2);
    if (unit === 1) return "book1";
    if (unit === 2) return "book2";
    if (unit === 3) return "book3";
  }
  return "book1";
}

export function getBadgeImagePath(
  badgeId: BadgeId,
  bookId?: string | null,
  week?: number | null,
): string {
  const book = resolveBadgeBookId(bookId, week);
  return BADGE_IMAGES_BY_BOOK[book][badgeId] ?? BADGE_CONFIG[badgeId].svgPath;
}

/** Home week-card medal counter icon (book-themed 🏅 replacement). */
const HOME_MEDAL_BY_BOOK: Record<BadgeBookId, string> = {
  book1: "/images/orid/badges/home_medal_book1.png",
  book2: "/images/orid/badges/home_medal_book2.png",
  book3: "/images/orid/badges/home_medal_book3.png",
};

export function getHomeMedalImagePath(
  bookId?: string | null,
  week?: number | null,
): string {
  return HOME_MEDAL_BY_BOOK[resolveBadgeBookId(bookId, week)];
}

/** Config with book-specific image + display name when available. */
export function getBadgeConfigForBook(
  badgeId: BadgeId,
  bookId?: string | null,
  week?: number | null,
): BadgeConfig {
  const base = BADGE_CONFIG[badgeId];
  const book = resolveBadgeBookId(bookId, week);
  const names =
    book === "book2"
      ? BOOK2_BADGE_NAMES[badgeId]
      : book === "book3"
        ? BOOK3_BADGE_NAMES[badgeId]
        : undefined;
  return {
    ...base,
    ...(names ?? {}),
    svgPath: getBadgeImagePath(badgeId, book, week),
  };
}

export const BADGE_CONFIG: Record<BadgeId, BadgeConfig> = {
  badge_start: {
    id: "badge_start",
    name: "下筆柿子章",
    unlockHint: "寫下一段內容，並使用一次寫作引導，就可以獲得。",
    earnedHint: "已獲得：你已經開始寫，也用過引導了！",
    modalTitle: "恭喜獲得下筆徽章！",
    modalText: "你已經開始寫下自己的想法，也使用了寫作引導。接下來把故事裡「誰做了什麼」寫清楚吧！",
    svgPath: "/images/orid/badges/badge_persimmon_start.png",
  },
  badge_30: {
    id: "badge_30",
    name: "柿子銅徽章",
    unlockHint: "完成「觀察」格：寫清楚故事裡的人物、事件或情節，就可以獲得。",
    earnedHint: "已獲得：你已經把故事裡的人物和事件說清楚了！",
    modalTitle: "恭喜獲得柿子銅徽章！",
    modalText: "你已經把故事裡的人物和事件說清楚了。接下來可以寫寫看：你有什麼感受？為什麼？",
    svgPath: "/images/orid/badges/badge_persimmon_bronze.png",
  },
  badge_60: {
    id: "badge_60",
    name: "柿子銀徽章",
    unlockHint: "完成「觀察、感受、體會」三格：寫出事件、感受原因，以及你的想法，就可以獲得。",
    earnedHint: "已獲得：你已經寫出事件、感受與體會了！",
    modalTitle: "恭喜獲得柿子銀徽章！",
    modalText: "你已經寫出事件、感受，也說出從故事學到的道理。接下來可以寫一個生活裡做得到的小行動。",
    svgPath: "/images/orid/badges/badge_persimmon_silver.png",
  },
  badge_90: {
    id: "badge_90",
    name: "柿子金徽章",
    unlockHint: "完成「觀察、感受、體會、行動」四格反思，就可以獲得。",
    earnedHint: "已獲得：你已經走完一整趟反思寫作！",
    modalTitle: "恭喜獲得柿子金徽章！",
    modalText: "太棒了！你已經把觀察、感受、體會和行動都寫完了。",
    svgPath: "/images/orid/badges/badge_persimmon_gold.png",
  },
  badge_synthesis_content: {
    id: "badge_synthesis_content",
    name: "內容整合章",
    unlockHint: "寫出故事事件、自己的想法、體會與行動，並讓它們彼此有關。",
    earnedHint: "已獲得：你已把故事、想法、體會與行動整合成一篇！",
    modalTitle: "恭喜獲得內容整合章！",
    modalText: "你已經把故事事件、自己的想法、學到的體會和未來行動整合起來了。",
    svgPath: "/images/orid/badges/badge_persimmon_start.png",
  },
  badge_synthesis_coherence: {
    id: "badge_synthesis_coherence",
    name: "文章連貫章",
    unlockHint: "調整文章順序和前後連接，讓讀者能順利讀懂。",
    earnedHint: "已獲得：讀者可以順著文章讀懂前後關係！",
    modalTitle: "恭喜獲得文章連貫章！",
    modalText: "你的文章順序清楚，故事、感受、體會和行動能自然接起來。",
    svgPath: "/images/orid/badges/badge_persimmon_bronze.png",
  },
  badge_synthesis_reflection: {
    id: "badge_synthesis_reflection",
    name: "反思深度章",
    unlockHint: "不只說發生什麼，也用故事說明自己的感受、想法或學習原因。",
    earnedHint: "已獲得：你已說清楚自己為什麼這樣想！",
    modalTitle: "恭喜獲得反思深度章！",
    modalText: "你能用故事裡的事情說明自己的感受、想法或學習原因。",
    svgPath: "/images/orid/badges/badge_persimmon_silver.png",
  },
  badge_synthesis_action: {
    id: "badge_synthesis_action",
    name: "行動應用章",
    unlockHint: "提出自己能做到、具體可行，而且呼應故事體會的行動。",
    earnedHint: "已獲得：你已把學到的事變成自己能做到的行動！",
    modalTitle: "恭喜獲得行動應用章！",
    modalText: "你提出了一個具體、可行，而且能呼應故事體會的行動。",
    svgPath: "/images/orid/badges/badge_persimmon_gold.png",
  },
};

// ---------------------------------------------------------------------------
// Pure logic helpers
// ---------------------------------------------------------------------------

export interface BadgeEvalInput {
  hasWritingContent: boolean;
  hasUsedFeedbackOrPrompt: boolean;
  /** Completed ORID stages (O/R/I/D). */
  stagesPassed?: Iterable<string> | null;
}

const STAGE_KEYS = new Set(["O", "R", "I", "D"]);

export function normalizeStageSet(stages?: Iterable<string> | null): Set<OridStageKey> {
  const out = new Set<OridStageKey>();
  for (const s of stages ?? []) {
    const u = String(s || "")
      .trim()
      .toUpperCase();
    if (STAGE_KEYS.has(u)) out.add(u as OridStageKey);
  }
  return out;
}

/** Experimental: stage counts if any draft feedback.ok is true. */
export function stagesPassedFromWritingOk(writing: {
  stages?: Record<string, { feedback?: Record<string, { ok?: boolean } | null> | null } | null>;
} | null | undefined): OridStageKey[] {
  const passed: OridStageKey[] = [];
  const stages = writing?.stages;
  if (!stages) return passed;
  for (const key of ["O", "R", "I", "D"] as const) {
    const stageObj = stages[key];
    const feedback = stageObj?.feedback;
    if (!feedback) continue;
    for (const fb of Object.values(feedback)) {
      if (fb && fb.ok === true) {
        passed.push(key);
        break;
      }
    }
  }
  return passed;
}

/** Control: stage counts if d1/d2 has non-empty text. */
export function stagesPassedFromWritingContent(writing: {
  stages?: Record<string, { d1?: string | null; d2?: string | null } | null>;
} | null | undefined): OridStageKey[] {
  const passed: OridStageKey[] = [];
  const stages = writing?.stages;
  if (!stages) return passed;
  for (const key of ["O", "R", "I", "D"] as const) {
    const stageObj = stages[key];
    const text = `${stageObj?.d1 ?? ""}${stageObj?.d2 ?? ""}`.trim();
    if (text) passed.push(key);
  }
  return passed;
}

/** Return the list of badge IDs earned given current state. */
export function calculateEarnedBadges(input: BadgeEvalInput): BadgeId[] {
  const earned: BadgeId[] = [];
  const { hasWritingContent, hasUsedFeedbackOrPrompt, stagesPassed } = input;

  if (hasWritingContent && hasUsedFeedbackOrPrompt) {
    earned.push("badge_start");
  }

  const passed = normalizeStageSet(stagesPassed);
  if (passed.has("O")) earned.push("badge_30");
  if (passed.has("O") && passed.has("R") && passed.has("I")) earned.push("badge_60");
  if (passed.has("O") && passed.has("R") && passed.has("I") && passed.has("D")) {
    earned.push("badge_90");
  }
  return earned;
}

export type SynthesisCriterionId =
  | "content_integration"
  | "coherence"
  | "reflection_depth"
  | "action_application";

const SYNTHESIS_BADGE_BY_CRITERION: Record<SynthesisCriterionId, BadgeId> = {
  content_integration: "badge_synthesis_content",
  coherence: "badge_synthesis_coherence",
  reflection_depth: "badge_synthesis_reflection",
  action_application: "badge_synthesis_action",
};

/** Even-week quality badges: one per rubric criterion at level 3 or 4. */
export function calculateEarnedSynthesisBadges(
  levels: Partial<Record<SynthesisCriterionId, number>>,
): BadgeId[] {
  return (Object.keys(SYNTHESIS_BADGE_BY_CRITERION) as SynthesisCriterionId[])
    .filter((criterion) => Number(levels[criterion] ?? 0) >= 3)
    .map((criterion) => SYNTHESIS_BADGE_BY_CRITERION[criterion]);
}

/** Return badges in current that are NOT in previous. */
export function getNewlyEarnedBadges(
  previous: BadgeId[],
  current: BadgeId[],
): BadgeId[] {
  const prevSet = new Set(previous);
  return current.filter((b) => !prevSet.has(b));
}

/** True if there are newly earned badges to show a modal for. */
export function shouldShowBadgeModal(newBadges: BadgeId[]): boolean {
  return newBadges.length > 0;
}
