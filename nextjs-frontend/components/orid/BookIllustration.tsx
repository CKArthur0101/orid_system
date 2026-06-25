import Image from "next/image";

import { getBookWeekArt } from "@/lib/orid-book-art";

export function BookIllustration({
  week,
  variant = "scene",
  layout = "default",
  className,
  imageClassName,
}: {
  week: number;
  variant?: "scene" | "helper";
  layout?: "default" | "hero";
  className?: string;
  imageClassName?: string;
}) {
  const art = getBookWeekArt(week);
  if (!art) return null;

  const src = variant === "helper" ? art.helper : art.scene;
  const size = variant === "helper" ? 120 : layout === "hero" ? 320 : 200;
  const isHero = layout === "hero" && variant === "scene";

  return (
    <div
      className={[
        "overflow-hidden rounded-2xl border border-amber-200/70 bg-white shadow-sm",
        isHero ? "flex h-full w-full items-center justify-center p-1" : "p-1.5",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <Image
        src={src}
        alt={art.alt}
        width={size}
        height={size}
        className={[
          isHero ? "h-[92%] w-[92%] object-contain object-center" : "h-auto w-full object-contain",
          imageClassName,
        ]
          .filter(Boolean)
          .join(" ")}
      />
    </div>
  );
}

export function BookHelperAvatar({
  week,
  size = 56,
  className,
}: {
  week: number;
  size?: number;
  className?: string;
}) {
  const art = getBookWeekArt(week);
  if (!art) return null;

  return (
    <div
      className={[
        "shrink-0 overflow-hidden rounded-2xl border border-amber-200/60 bg-white p-0.5 shadow-sm",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <Image
        src={art.helper}
        alt="松果小夥伴"
        width={size}
        height={size}
        className="object-contain"
        style={{ width: size, height: size }}
      />
    </div>
  );
}
