export const BOOK_WEEK_ART: Record<
  number,
  {
    scene: string;
    helper: string;
    persimmonBullet: string;
    alt: string;
    /** Small thumbnail for week-selection cards (64 px). */
    coverThumb?: string;
    title?: string;
  } | undefined
> = {
  1: {
    scene: "/images/orid/week1/week1-persimmon-scene.png",
    helper: "/images/orid/week1/week1-squirrel-helper.png",
    persimmonBullet: "/images/orid/week1/week1-persimmon-bullet.png",
    coverThumb: "/images/orid/dashboard/week1-card-thumb.png",
    title: "阿松爺爺的柿子樹",
    alt: "阿松爺爺的柿子樹故事插圖",
  },
  3: {
    scene: "/images/orid/week3/week3-zhu-family-scene.png",
    helper: "/images/orid/week3/week3-squirrel-helper.png",
    persimmonBullet: "/images/orid/week1/week1-persimmon-bullet.png",
    coverThumb: "/images/orid/week3/week3-zhu-family-scene.png",
    title: "朱家故事",
    alt: "朱家故事插圖",
  },
  4: {
    scene: "/images/orid/week3/week3-zhu-family-scene.png",
    helper: "/images/orid/week3/week3-squirrel-helper.png",
    persimmonBullet: "/images/orid/week1/week1-persimmon-bullet.png",
    coverThumb: "/images/orid/week3/week3-squirrel-helper.png",
    title: "朱家故事（整合寫作）",
    alt: "朱家故事插圖",
  },
};

export function getBookWeekArt(week: number) {
  return BOOK_WEEK_ART[week];
}
