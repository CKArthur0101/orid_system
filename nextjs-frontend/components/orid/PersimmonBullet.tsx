import Image from "next/image";

import { getBookWeekArt } from "@/lib/orid-book-art";

const FALLBACK = "/images/orid/week1/week1-persimmon-bullet.png";

export function PersimmonBullet({ size = 18, className }: { size?: number; className?: string }) {
  const art = getBookWeekArt(1);
  const src = art?.persimmonBullet ?? FALLBACK;

  return (
    <Image
      src={src}
      alt=""
      width={size}
      height={size}
      aria-hidden
      className={["shrink-0 object-contain", className].filter(Boolean).join(" ")}
      style={{ width: size, height: size, minWidth: size, minHeight: size }}
    />
  );
}
