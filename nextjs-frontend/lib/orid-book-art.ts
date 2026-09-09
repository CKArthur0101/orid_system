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
    coverThumb: "/images/orid/week1/week1-persimmon-scene.png",
    title: "阿松爺爺的柿子樹",
    alt: "阿松爺爺的柿子樹故事插圖",
  },
  2: {
    scene: "/images/orid/week1/week2-synthesis-cover.png",
    helper: "/images/orid/week1/week1-squirrel-helper.png",
    persimmonBullet: "/images/orid/week1/week1-persimmon-bullet.png",
    coverThumb: "/images/orid/week1/week2-synthesis-cover.png",
    title: "阿松爺爺的柿子樹（整合寫作）",
    alt: "阿松爺爺的柿子樹整合寫作插圖",
  },
  3: {
    scene: "/images/orid/week3/week3-zhu-family-scene.png",
    helper: "/images/orid/week3/week3-zhu-mama-helper.png",
    persimmonBullet: "/images/orid/week3/week3-pig-bullet.png",
    coverThumb: "/images/orid/week3/week3-zhu-family-scene.png",
    title: "朱家故事",
    alt: "朱家故事插圖",
  },
  4: {
    scene: "/images/orid/week3/week4-zhu-family-synthesis.png",
    helper: "/images/orid/week3/week3-zhu-mama-helper.png",
    persimmonBullet: "/images/orid/week3/week3-pig-bullet.png",
    coverThumb: "/images/orid/week3/week4-zhu-family-synthesis.png",
    title: "朱家故事（整合寫作）",
    alt: "朱家故事整合寫作插圖",
  },
  5: {
    scene: "/images/orid/week5/week5-lion-scene.png",
    helper: "/images/orid/week5/week5-lion-helper.png",
    persimmonBullet: "/images/orid/week1/week1-persimmon-bullet.png",
    coverThumb: "/images/orid/week5/week5-lion-scene.png",
    title: "不會寫字的獅子",
    alt: "不會寫字的獅子故事插圖",
  },
  6: {
    scene: "/images/orid/week5/week6-lion-synthesis.png",
    helper: "/images/orid/week5/week5-lion-helper.png",
    persimmonBullet: "/images/orid/week1/week1-persimmon-bullet.png",
    coverThumb: "/images/orid/week5/week6-lion-synthesis.png",
    title: "不會寫字的獅子（整合寫作）",
    alt: "不會寫字的獅子整合寫作插圖",
  },
};

export function getBookWeekArt(week: number) {
  return BOOK_WEEK_ART[week];
}
