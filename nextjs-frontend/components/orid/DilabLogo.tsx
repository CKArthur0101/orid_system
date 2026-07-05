import Image from "next/image";

/** Full DILab 資料洞察 logo — amber recolor, transparent background. */
export const DILAB_BRAND = {
  logo: "/images/brand/dilab-logo-amber.png",
  /** width / height after trim ≈ 890 / 809 */
  aspectRatio: 890 / 809,
} as const;

export function DilabLogo({
  height = 36,
  className,
}: {
  height?: number;
  className?: string;
}) {
  const width = Math.round(height * DILAB_BRAND.aspectRatio);

  return (
    <Image
      src={DILAB_BRAND.logo}
      alt="DILab 資料洞察"
      width={width}
      height={height}
      className={["shrink-0 object-contain object-left", className].filter(Boolean).join(" ")}
      style={{ height, width: "auto", maxHeight: height }}
      priority
    />
  );
}
