import { bookUnitFromWeek, getWeekPlan } from "@/lib/orid/week-flow";

type BookWeekArt = {
  scene: string;
  helper: string;
  persimmonBullet: string;
  alt: string;
  /** Small thumbnail for week-selection cards (64 px). */
  coverThumb?: string;
  title?: string;
};

type BookArtSet = {
  title: string;
  oridScene: string;
  synthesisScene: string;
  helper: string;
  bullet: string;
};

/** One art set per book; weeks map onto books through the week plan. */
const BOOK_ART: Record<number, BookArtSet> = {
  1: {
    title: "阿松爺爺的柿子樹",
    oridScene: "/images/orid/week1/week1-persimmon-scene.png",
    synthesisScene: "/images/orid/week1/week2-synthesis-cover.png",
    helper: "/images/orid/week1/week1-squirrel-helper.png",
    bullet: "/images/orid/week1/week1-persimmon-bullet.png",
  },
  2: {
    title: "朱家故事",
    oridScene: "/images/orid/week3/week3-zhu-family-scene.png",
    synthesisScene: "/images/orid/week3/week4-zhu-family-synthesis.png",
    helper: "/images/orid/week3/week3-zhu-mama-helper.png",
    bullet: "/images/orid/week3/week3-pig-bullet.png",
  },
  3: {
    title: "不會寫字的獅子",
    oridScene: "/images/orid/week5/week5-lion-scene.png",
    synthesisScene: "/images/orid/week5/week6-lion-synthesis.png",
    helper: "/images/orid/week5/week5-lion-helper.png",
    bullet: "/images/orid/week5/week5-lion-bullet.png",
  },
};

function buildWeekArt(week: number): BookWeekArt | undefined {
  const plan = getWeekPlan(week);
  if (!plan) return undefined;
  const art = BOOK_ART[plan.bookUnit];
  if (!art) return undefined;
  const synthesis = plan.kind === "synthesis";
  const scene =
    week === 2
      ? "/images/orid/week1/week2-id-scene.png"
      : synthesis
        ? art.synthesisScene
        : art.oridScene;
  return {
    scene,
    helper: art.helper,
    persimmonBullet: art.bullet,
    coverThumb: scene,
    title: synthesis ? `${art.title}（整合寫作）` : art.title,
    alt: week === 2 ? "阿松爺爺捧著一籃柿子" : synthesis ? `${art.title}整合寫作插圖` : `${art.title}故事插圖`,
  };
}

export const BOOK_WEEK_ART: Record<number, BookWeekArt | undefined> = Object.fromEntries(
  [1, 2, 3, 4, 5, 6, 7].map((w) => [w, buildWeekArt(w)]),
);

export function partnerVoice(week: number): { name: string; hello: string; thinking: string } {
  const unit = bookUnitFromWeek(week);
  if (unit === 3) {
    return { name: "小獅子", hello: "你好！我是小獅子", thinking: "小獅子正在想…" };
  }
  if (unit === 2) {
    return { name: "朱媽媽", hello: "你好！我是朱媽媽", thinking: "朱媽媽正在想…" };
  }
  return {
    name: "松果小夥伴",
    hello: "你好！我是松果小夥伴 🌰",
    thinking: "松果小幫手正在思考…",
  };
}

export function getBookWeekArt(week: number) {
  return BOOK_WEEK_ART[week];
}
