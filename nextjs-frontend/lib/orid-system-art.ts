import { getWeekPlan } from "@/lib/orid/week-flow";

/** System-level illustration paths (forest reflection journey theme). */
export const SYSTEM_ILLUSTRATIONS = {
  reading: "/images/orid/system/system-reading.png",
  thinking: "/images/orid/system/system-thinking.png",
} as const;

export type SystemIllustrationKey = keyof typeof SYSTEM_ILLUSTRATIONS;

export const DASHBOARD_ART = {
  weeklyReadingIcon: "/images/orid/dashboard/weekly-reading-icon.png",
  book1OridThumb: "/images/orid/week1/week1-persimmon-scene.png",
  book1SynthesisThumb: "/images/orid/week1/week2-synthesis-cover.png",
  book2OridThumb: "/images/orid/week3/week3-zhu-family-scene.png",
  book2SynthesisThumb: "/images/orid/week3/week4-zhu-family-synthesis.png",
  book3OridThumb: "/images/orid/week5/week5-lion-scene.png",
  book3SynthesisThumb: "/images/orid/week5/week6-lion-synthesis.png",
} as const;

type BookMeta = { title: string; oridThumb: string; synthesisThumb: string; accentColor: string };

const BOOK_META: Record<number, BookMeta> = {
  1: {
    title: "阿松爺爺的柿子樹",
    oridThumb: DASHBOARD_ART.book1OridThumb,
    synthesisThumb: DASHBOARD_ART.book1SynthesisThumb,
    accentColor: "#d97706",
  },
  2: {
    title: "朱家故事",
    oridThumb: DASHBOARD_ART.book2OridThumb,
    synthesisThumb: DASHBOARD_ART.book2SynthesisThumb,
    accentColor: "#ea580c",
  },
  3: {
    title: "不會寫字的獅子",
    oridThumb: DASHBOARD_ART.book3OridThumb,
    synthesisThumb: DASHBOARD_ART.book3SynthesisThumb,
    accentColor: "#b45309",
  },
};

export type WeekBookMeta = { title?: string; coverThumb?: string; accentColor?: string; subtitle?: string };

/** Per-week book metadata derived from the week plan. Weeks without a plan show a placeholder. */
export function getWeekBookMeta(week: number): WeekBookMeta {
  const plan = getWeekPlan(week);
  const book = plan ? BOOK_META[plan.bookUnit] : undefined;
  if (!plan || !book) return {};
  const synthesis = plan.kind === "synthesis";
  const week2Scene = "/images/orid/week1/week2-id-scene.png";
  return {
    title: synthesis ? `${book.title}（整合寫作）` : book.title,
    coverThumb: week === 2 ? week2Scene : synthesis ? book.synthesisThumb : book.oridThumb,
    accentColor: book.accentColor,
    subtitle: plan.subtitle,
  };
}
