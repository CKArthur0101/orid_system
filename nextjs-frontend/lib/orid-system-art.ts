/** System-level illustration paths (forest reflection journey theme). */
export const SYSTEM_ILLUSTRATIONS = {
  reading: "/images/orid/system/system-reading.png",
  thinking: "/images/orid/system/system-thinking.png",
} as const;

export type SystemIllustrationKey = keyof typeof SYSTEM_ILLUSTRATIONS;

export const DASHBOARD_ART = {
  weeklyReadingIcon: "/images/orid/dashboard/weekly-reading-icon.png",
  week1CardThumb: "/images/orid/dashboard/week1-card-thumb.png",
} as const;

/** Per-week book metadata. Weeks without a title show a placeholder. */
export const WEEK_BOOK_META: Record<
  number,
  { title?: string; coverThumb?: string; accentColor?: string }
> = {
  1: {
    title: "阿松爺爺的柿子樹",
    coverThumb: DASHBOARD_ART.week1CardThumb,
    accentColor: "#d97706",
  },
  2: {
    title: "整合寫作",
    coverThumb: SYSTEM_ILLUSTRATIONS.reading,
  },
};

export function getWeekBookMeta(week: number) {
  return WEEK_BOOK_META[week] ?? {};
}
