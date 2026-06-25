export const BOOK_WEEK_ART: Record<
  number,
  { scene: string; helper: string; persimmonBullet: string; alt: string } | undefined
> = {
  1: {
    scene: "/images/orid/week1/week1-persimmon-scene.png",
    helper: "/images/orid/week1/week1-squirrel-helper.png",
    persimmonBullet: "/images/orid/week1/week1-persimmon-bullet.png",
    alt: "阿松爺爺的柿子樹故事插圖",
  },
};

export function getBookWeekArt(week: number) {
  return BOOK_WEEK_ART[week];
}
