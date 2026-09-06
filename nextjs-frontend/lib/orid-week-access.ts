/**
 * 學生端「第幾週已開放」：首頁、閱讀選單、週次內頁需共用此常數，避免不同頁顯示不一致。
 */
export const ORID_TOTAL_WEEKS = 6;

/** 已開放週次上限（含）：1..ORID_UNLOCKED_WEEKS 可進入。 */
export const ORID_UNLOCKED_WEEKS = 4;

export function oridWeekIsAccessible(week: number): boolean {
  return Number.isFinite(week) && week >= 1 && week <= ORID_UNLOCKED_WEEKS;
}
