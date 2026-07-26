import Image from "next/image";

/** Scattered login decorations — intentionally offset, not grid-aligned. */
const DECOR = [
  {
    src: "/images/orid/login/login-deco-tl.png",
    alt: "",
    className: "absolute left-[1%] top-[4%] w-[148px] sm:left-[3%] sm:top-[7%] sm:w-[172px] lg:w-[200px]",
    rotate: -14,
    floatClass: "orid-login-float-y",
    delay: "0s",
  },
  {
    src: "/images/orid/login/login-deco-tr.png",
    alt: "",
    className: "absolute right-[2%] top-[16%] w-[132px] sm:right-[5%] sm:top-[22%] sm:w-[158px] lg:w-[188px]",
    rotate: 17,
    floatClass: "orid-login-float-x",
    delay: "0.6s",
  },
  {
    src: "/images/orid/login/lazy-squirrel.png",
    alt: "",
    className: "absolute bottom-[10%] left-[5%] w-[140px] sm:bottom-[12%] sm:left-[9%] sm:w-[168px] lg:w-[196px]",
    rotate: -4,
    floatClass: "orid-login-float-yx",
    delay: "1.1s",
  },
  {
    src: "/images/orid/login/login-deco-br.png",
    alt: "",
    className: "absolute -bottom-[2%] right-[0%] w-[158px] sm:bottom-[6%] sm:right-[2%] sm:w-[182px] lg:w-[208px]",
    rotate: -11,
    floatClass: "orid-login-float-xy",
    delay: "0.3s",
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
          <div className={item.floatClass} style={{ animationDelay: item.delay }}>
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
        </div>
      ))}
    </div>
  );
}
