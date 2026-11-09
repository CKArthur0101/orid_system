/**
 * 學生端「第幾週已開放」：首頁、閱讀選單、週次內頁需共用此常數，避免不同頁顯示不一致。
 */
import { DEMO_WEEK, ORID_TOTAL_WEEKS as PLAN_TOTAL_WEEKS } from "@/lib/orid/week-flow";

export const ORID_TOTAL_WEEKS = PLAN_TOTAL_WEEKS;

/** 正式實驗已開放週次上限（含）：1..ORID_UNLOCKED_WEEKS 可進入。0 = 全部鎖住。 */
export const ORID_UNLOCKED_WEEKS = 0;

/** 系統練習／說明用體驗週是否開放（與正式 1–7 分開）。 */
export const ORID_DEMO_WEEK_OPEN = true;

/** 前測／後測電子書是否可點開。說明階段先關閉，仍顯示書名。 */
export const ORID_PRETEST_OPEN = false;
export const ORID_POSTTEST_OPEN = false;

export function oridWeekIsAccessible(week: number): boolean {
  if (!Number.isFinite(week)) return false;
  if (week === DEMO_WEEK) return ORID_DEMO_WEEK_OPEN;
  return week >= 1 && week <= ORID_UNLOCKED_WEEKS;
}

export function oridAssessmentIsOpen(kind: "pre" | "post"): boolean {
  return kind === "pre" ? ORID_PRETEST_OPEN : ORID_POSTTEST_OPEN;
}
