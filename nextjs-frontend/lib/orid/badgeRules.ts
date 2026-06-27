/**
 * Frontend badge rules — mirrors backend orid_badges.py.
 * Tooltip and modal copy is centralised here.
 */

export type BadgeId = "badge_start" | "badge_30" | "badge_60" | "badge_90";

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

export const BADGE_ORDER: BadgeId[] = ["badge_start", "badge_30", "badge_60", "badge_90"];

export const BADGE_CONFIG: Record<BadgeId, BadgeConfig> = {
  badge_start: {
    id: "badge_start",
    name: "下筆徽章",
    unlockHint: "開始寫作，並使用一次回饋或提示，就可以獲得。",
    earnedHint: "已獲得：你已經達成這個階段！",
    modalTitle: "恭喜獲得下筆徽章！",
    modalText: "你已經開始寫下自己的想法，也使用了寫作引導，繼續完成今天的反思任務吧！",
    svgPath: "/images/orid/badges/badge_start.svg",
  },
  badge_30: {
    id: "badge_30",
    name: "松果銅徽章",
    unlockHint: "總分達到 30/90，就可以獲得。",
    earnedHint: "已獲得：你已經達成這個階段！",
    modalTitle: "恭喜獲得松果銅徽章！",
    modalText: "你已經完成基本的反思內容，接下來可以試著寫得更具體。",
    svgPath: "/images/orid/badges/badge_30.svg",
  },
  badge_60: {
    id: "badge_60",
    name: "松果銀徽章",
    unlockHint: "總分達到 60/90，就可以獲得。",
    earnedHint: "已獲得：你已經達成這個階段！",
    modalTitle: "恭喜獲得松果銀徽章！",
    modalText: "你的反思越來越完整了，可以再加強想法之間的連結。",
    svgPath: "/images/orid/badges/badge_60.svg",
  },
  badge_90: {
    id: "badge_90",
    name: "松果金徽章",
    unlockHint: "總分達到 90/90，就可以獲得。",
    earnedHint: "已獲得：你已經達成這個階段！",
    modalTitle: "恭喜獲得松果金徽章！",
    modalText: "太棒了！你的反思內容很完整，也能連結感受、體會與行動。",
    svgPath: "/images/orid/badges/badge_90.svg",
  },
};

// ---------------------------------------------------------------------------
// Pure logic helpers
// ---------------------------------------------------------------------------

export interface BadgeEvalInput {
  hasWritingContent: boolean;
  hasUsedFeedbackOrPrompt: boolean;
  totalScore: number | null;
}

/** Return the list of badge IDs earned given current state. */
export function calculateEarnedBadges(input: BadgeEvalInput): BadgeId[] {
  const earned: BadgeId[] = [];
  const { hasWritingContent, hasUsedFeedbackOrPrompt, totalScore } = input;

  if (hasWritingContent && hasUsedFeedbackOrPrompt) {
    earned.push("badge_start");
  }
  if (totalScore != null) {
    if (totalScore >= 30) earned.push("badge_30");
    if (totalScore >= 60) earned.push("badge_60");
    if (totalScore >= 90) earned.push("badge_90");
  }
  return earned;
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
