/** 學生登入後首頁（每週閱讀選單） */
export const STUDENT_HOME = "/home";

/** 學生週次寫作頁前綴 */
export const STUDENT_WEEK_PREFIX = "/week";

/** 學生週次寫作頁 */
export function studentWeekPath(week: number): string {
  return `${STUDENT_WEEK_PREFIX}/${week}`;
}

/** 是否為學生週次寫作頁（鎖定全屏寫作 layout 用） */
export function isStudentWeekWritingPath(pathname: string | null | undefined): boolean {
  if (!pathname) return false;
  return /^\/week\/\d+/.test(pathname);
}
