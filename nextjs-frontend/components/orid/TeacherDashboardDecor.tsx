import Image from "next/image";

/**
 * Header deco beside title — compact, does not extend page height.
 * Hidden on very small phones to keep the title row readable.
 */
export function TeacherDashboardHeaderDecor() {
  return (
    <div className="pointer-events-none hidden shrink-0 sm:block" aria-hidden>
      <div className="orid-login-float-y" style={{ animationDelay: "0.2s" }}>
        <Image
          src="/images/orid/teacher/teacher-deco-squirrel-pinecone.png"
          alt=""
          width={88}
          height={88}
          className="h-[64px] w-auto drop-shadow-sm md:h-[72px] lg:h-[84px]"
          style={{ objectFit: "contain" }}
          priority
        />
      </div>
    </div>
  );
}

/**
 * Left/right side decorations fixed to the viewport.
 * z above main content so tablet cards cannot cover them; below sticky header.
 * Hidden on phones (< md) to avoid crowding.
 */
export function TeacherDashboardSideDecor() {
  return (
    <div className="pointer-events-none fixed inset-0 z-20 overflow-hidden" aria-hidden>
      {/* Left: lazy squirrel (irasutoya-style) */}
      <div
        className={[
          "absolute left-[max(0.5rem,env(safe-area-inset-left))]",
          "bottom-[max(1rem,env(safe-area-inset-bottom))]",
          "hidden md:block md:w-[110px] md:opacity-95",
          "lg:bottom-8 lg:left-5 lg:w-[140px]",
        ].join(" ")}
      >
        <div className="orid-login-float-yx" style={{ animationDelay: "0.7s" }}>
          <Image
            src="/images/orid/teacher/lazy-squirrel.png"
            alt=""
            width={200}
            height={120}
            className="h-auto w-full drop-shadow-md"
            style={{ objectFit: "contain" }}
          />
        </div>
      </div>

      {/* Right: squirrel with book */}
      <div
        className={[
          "absolute right-[max(0.5rem,env(safe-area-inset-right))]",
          "bottom-[max(1rem,env(safe-area-inset-bottom))]",
          "hidden md:block md:w-[100px] md:opacity-95",
          "lg:bottom-8 lg:right-5 lg:w-[132px]",
        ].join(" ")}
      >
        <div className="orid-login-float-xy" style={{ animationDelay: "1.1s" }}>
          <Image
            src="/images/orid/teacher/teacher-deco-squirrel-book.png"
            alt=""
            width={180}
            height={180}
            className="h-auto w-full drop-shadow-md"
            style={{ objectFit: "contain" }}
          />
        </div>
      </div>
    </div>
  );
}
