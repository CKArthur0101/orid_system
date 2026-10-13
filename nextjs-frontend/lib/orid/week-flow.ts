/**
 * Seven-week intervention plan (student-facing week numbers 1–7).
 *
 * Book 1 is split into three weeks: O/R, then I/D, then the integrated piece.
 * Books 2 and 3 keep one ORID week followed by one integration week.
 *
 *   1  阿松爺爺的柿子樹            O・R
 *   2  阿松爺爺的柿子樹            I・D   (reads week 1 O/R)
 *   3  阿松爺爺的柿子樹（整合寫作）       (reads week 1 O/R + week 2 I/D)
 *   4  朱家故事                    O・R・I・D
 *   5  朱家故事（整合寫作）               (reads week 4)
 *   6  不會寫字的獅子              O・R・I・D
 *   7  不會寫字的獅子（整合寫作）         (reads week 6)
 *
 * Keep this file in sync with fastapi_backend/app/content/week_plan.py.
 */

export type OridStageKey = "O" | "R" | "I" | "D";
export type WeekKind = "orid" | "synthesis";

export interface WeekPlan {
  week: number;
  kind: WeekKind;
  /** 1-based book unit: 1 柿子樹, 2 朱家, 3 獅子. */
  bookUnit: number;
  /** Stages the student writes this week (empty for integration weeks). */
  stages: OridStageKey[];
  /** Earlier weeks whose saved ORID text is shown read-only this week. */
  referenceWeeks: number[];
  /** Home-card subtitle for split weeks. */
  subtitle?: string;
}

export const ORID_TOTAL_WEEKS = 7;

const ALL_STAGES: OridStageKey[] = ["O", "R", "I", "D"];

export const WEEK_PLAN: Record<number, WeekPlan> = {
  1: { week: 1, kind: "orid", bookUnit: 1, stages: ["O", "R"], referenceWeeks: [], subtitle: "O・R 觀察與感受" },
  2: { week: 2, kind: "orid", bookUnit: 1, stages: ["I", "D"], referenceWeeks: [1], subtitle: "I・D 詮釋與決定" },
  3: { week: 3, kind: "synthesis", bookUnit: 1, stages: [], referenceWeeks: [1, 2] },
  4: { week: 4, kind: "orid", bookUnit: 2, stages: ALL_STAGES, referenceWeeks: [] },
  5: { week: 5, kind: "synthesis", bookUnit: 2, stages: [], referenceWeeks: [4] },
  6: { week: 6, kind: "orid", bookUnit: 3, stages: ALL_STAGES, referenceWeeks: [] },
  7: { week: 7, kind: "synthesis", bookUnit: 3, stages: [], referenceWeeks: [6] },
};

export function getWeekPlan(week: number): WeekPlan | undefined {
  return WEEK_PLAN[week];
}

/** Weeks where the student writes O/R/I/D cards (all or a subset). */
export const isOridWeek = (w: number): boolean => WEEK_PLAN[w]?.kind === "orid";

/** Weeks where the student writes the integrated reflection. */
export const isSynthesisWeek = (w: number): boolean => WEEK_PLAN[w]?.kind === "synthesis";

/** Stages the student can type into this week. */
export function writableStages(w: number): OridStageKey[] {
  return WEEK_PLAN[w]?.stages ?? [];
}

export function isStageWritable(w: number, stage: OridStageKey): boolean {
  return writableStages(w).includes(stage);
}

/** Weeks whose saved ORID cards are displayed read-only this week. */
export function referenceWeeks(w: number): number[] {
  return WEEK_PLAN[w]?.referenceWeeks ?? [];
}

/**
 * Which week holds the saved text for `stage` when viewed from `w`.
 * Returns `w` itself when the stage is writable this week.
 */
export function stageSourceWeek(w: number, stage: OridStageKey): number | null {
  if (isStageWritable(w, stage)) return w;
  for (const ref of referenceWeeks(w)) {
    if (isStageWritable(ref, stage)) return ref;
  }
  return null;
}

/** 1-based book unit: weeks 1–3 → 1, 4–5 → 2, 6–7 → 3. */
export function bookUnitFromWeek(w: number): number {
  return WEEK_PLAN[w]?.bookUnit ?? 1;
}

/** Label such as 「第 1、2 週」 for read-only reference panels. */
export function referenceWeeksLabel(w: number): string {
  const refs = referenceWeeks(w);
  if (refs.length === 0) return `第 ${w} 週`;
  return `第 ${refs.join("、")} 週`;
}
