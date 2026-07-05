import Image from "next/image";

/** Scattered login decorations — intentionally offset, not grid-aligned. */
const DECOR = [
  {
    src: "/images/orid/login/login-deco-tl.png",
    alt: "",
    className: "absolute left-[1%] top-[4%] w-[148px] sm:left-[3%] sm:top-[7%] sm:w-[172px] lg:w-[200px]",
    rotate: -14,
  },
  {
    src: "/images/orid/login/login-deco-tr.png",
    alt: "",
    className: "absolute right-[2%] top-[16%] w-[132px] sm:right-[5%] sm:top-[22%] sm:w-[158px] lg:w-[188px]",
    rotate: 17,
  },
  {
    src: "/images/orid/login/login-deco-bl.png",
    alt: "",
    className: "absolute bottom-[11%] left-[7%] w-[126px] sm:bottom-[14%] sm:left-[11%] sm:w-[152px] lg:w-[178px]",
    rotate: 9,
  },
  {
    src: "/images/orid/login/login-deco-br.png",
    alt: "",
    className: "absolute -bottom-[2%] right-[0%] w-[158px] sm:bottom-[6%] sm:right-[2%] sm:w-[182px] lg:w-[208px]",
    rotate: -11,
  },
] as const;

export function LoginCornerDecorations() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
      {DECOR.map((item) => (
        <div
          key={item.src}
          className={item.className}
          style={{ transform: `rotate(${item.rotate}deg)` }}
        >
          <Image
            src={item.src}
            alt={item.alt}
            width={220}
            height={220}
            className="h-auto w-full drop-shadow-sm"
            style={{ objectFit: "contain" }}
            priority
          />
        </div>
      ))}
    </div>
  );
}
