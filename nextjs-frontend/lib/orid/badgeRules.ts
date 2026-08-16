/**
 * Frontend badge rules — mirrors backend orid_badges.py.
 * Tooltip and modal copy is centralised here.
 */

export type BadgeId =
  | "badge_start"
  | "badge_30"
  | "badge_60"
  | "badge_90"
  | "badge_synthesis_start";

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
  /** Path to SVG asset */
  svgPath: string;
}

export const BADGE_ORDER: BadgeId[] = [
  "badge_start",
  "badge_30",
  "badge_60",
  "badge_90",
  "badge_synthesis_start",
];

export const ORID_BADGE_ORDER: BadgeId[] = [
  "badge_start",
  "badge_30",
  "badge_60",
  "badge_90",
];

export const SYNTHESIS_BADGE_ORDER: BadgeId[] = [
  "badge_synthesis_start",
];

export const BADGE_CONFIG: Record<BadgeId, BadgeConfig> = {
  badge_start: {
    id: "badge_start",
    name: "下筆徽章",
    unlockHint: "寫下一段內容，並使用一次寫作引導，就可以獲得。",
    earnedHint: "已獲得：你已經開始寫，也用過引導了！",
    modalTitle: "恭喜獲得下筆徽章！",
    modalText: "你已經開始寫下自己的想法，也使用了寫作引導。接下來把故事裡「誰做了什麼」寫清楚吧！",
    svgPath: "/images/orid/badges/badge_start.svg",
  },
  badge_30: {
    id: "badge_30",
    name: "松果銅徽章",
    unlockHint: "完成「觀察」格：寫清楚故事裡的人物、事件或情節，就可以獲得。",
    earnedHint: "已獲得：你已經把故事裡的人物和事件說清楚了！",
    modalTitle: "恭喜獲得松果銅徽章！",
    modalText: "你已經把故事裡的人物和事件說清楚了。接下來可以寫寫看：你有什麼感受？為什麼？",
    svgPath: "/images/orid/badges/badge_30.svg",
  },
  badge_60: {
    id: "badge_60",
    name: "松果銀徽章",
    unlockHint: "完成「觀察、感受、體會」三格：寫出事件、感受原因，以及你的想法，就可以獲得。",
    earnedHint: "已獲得：你已經寫出事件、感受與體會了！",
    modalTitle: "恭喜獲得松果銀徽章！",
    modalText: "你已經寫出事件、感受，也說出從故事學到的道理。接下來可以寫一個生活裡做得到的小行動。",
    svgPath: "/images/orid/badges/badge_60.svg",
  },
  badge_90: {
    id: "badge_90",
    name: "松果金徽章",
    unlockHint: "完成「觀察、感受、體會、行動」四格反思，就可以獲得。",
    earnedHint: "已獲得：你已經走完一整趟反思寫作！",
    modalTitle: "恭喜獲得松果金徽章！",
    modalText: "太棒了！你已經把觀察、感受、體會和行動都寫完了。",
    svgPath: "/images/orid/badges/badge_90.svg",
  },
  // Even-week integration task badge — independent track from badge_30/60/90.
  badge_synthesis_start: {
    id: "badge_synthesis_start",
    name: "整合下筆章",
    unlockHint: "開始整合寫作，並使用一次整合寫作引導，就可以獲得。",
    earnedHint: "已獲得：你已經開始把上週的想法收成一篇，也問過小幫手了！",
    modalTitle: "恭喜獲得整合下筆章！",
    modalText:
      "你已經開始把上週的觀察、感受、體會和行動收成一篇文章，也使用了整合寫作的引導。接下來可以照建議調整一個地方，讓文章更順。",
    svgPath: "/images/orid/badges/badge_start.svg",
  },
};

// ---------------------------------------------------------------------------
// Pure logic helpers
// ---------------------------------------------------------------------------

export interface BadgeEvalInput {
  hasWritingContent: boolean;
  hasUsedFeedbackOrPrompt: boolean;
  /** Completed ORID stages (O/R/I/D). Prefer this over totalScore. */
  stagesPassed?: Iterable<string> | null;
  /** @deprecated Score no longer unlocks badges; kept for call-site compat. */
  totalScore?: number | null;
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

/** Even-week integration badge — independent of the O/R/I/D stage track. */
export function calculateEarnedSynthesisBadge(input: {
  hasSynthesisContent: boolean;
  hasUsedSynthesisGuide: boolean;
}): BadgeId[] {
  if (input.hasSynthesisContent && input.hasUsedSynthesisGuide) {
    return ["badge_synthesis_start"];
  }
  return [];
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
