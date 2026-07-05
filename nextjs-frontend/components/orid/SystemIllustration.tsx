import Image from "next/image";
import { SYSTEM_ILLUSTRATIONS, type SystemIllustrationKey } from "@/lib/orid-system-art";

interface SystemIllustrationProps {
  illustrationKey: SystemIllustrationKey;
  alt?: string;
  width?: number;
  height?: number;
  className?: string;
  priority?: boolean;
}

export function SystemIllustration({
  illustrationKey,
  alt = "",
  width = 240,
  height = 240,
  className,
  priority,
}: SystemIllustrationProps) {
  const src = SYSTEM_ILLUSTRATIONS[illustrationKey];

  return (
    <Image
      src={src}
      alt={alt}
      width={width}
      height={height}
      className={className}
      priority={priority}
      style={{ objectFit: "contain" }}
    />
  );
}
