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

  // Hero (寫作頁右上插圖)：去背透明，與登入裝飾同風格，不加白底卡片
  if (isHero) {
    return (
      <div
        className={[
          "flex h-full w-full items-center justify-center overflow-visible bg-transparent",
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
            "h-full w-full object-contain object-center drop-shadow-sm",
            imageClassName,
          ]
            .filter(Boolean)
            .join(" ")}
        />
      </div>
    );
  }

  return (
    <div
      className={[
        "overflow-hidden rounded-2xl border border-amber-200/70 bg-white/40 p-1.5 shadow-sm",
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
        className={["h-auto w-full object-contain", imageClassName].filter(Boolean).join(" ")}
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
    <div className={["shrink-0 overflow-visible bg-transparent", className].filter(Boolean).join(" ")}>
      <Image
        src={art.helper}
        alt="松果小夥伴"
        width={size}
        height={size}
        className="object-contain drop-shadow-sm"
        style={{ width: size, height: size }}
      />
    </div>
  );
}
