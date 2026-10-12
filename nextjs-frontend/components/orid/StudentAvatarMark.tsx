"use client";

import { useEffect, useState } from "react";

import {
  STUDENT_AVATAR_EVENT,
  avatarSrcForId,
  readActiveAvatarId,
} from "@/lib/orid/student-avatars";

export function useActiveStudentAvatarSrc() {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    const sync = () => setSrc(avatarSrcForId(readActiveAvatarId()));
    sync();
    window.addEventListener(STUDENT_AVATAR_EVENT, sync);
    return () => window.removeEventListener(STUDENT_AVATAR_EVENT, sync);
  }, []);

  return src;
}

export function StudentAvatarMark({
  src,
  size = 36,
  className = "",
}: {
  src: string | null;
  size?: number;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-amber-100 ring-2 ring-amber-200/80 ${className}`}
      style={{ width: size, height: size }}
    >
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt="" className="h-full w-full object-cover" />
      ) : (
        <svg viewBox="0 0 24 24" className="h-2/3 w-2/3 text-amber-800/45" aria-hidden>
          <circle cx="12" cy="9" r="3.2" fill="currentColor" />
          <path d="M6.5 18.5c.8-2.6 2.8-4 5.5-4s4.7 1.4 5.5 4" fill="currentColor" />
        </svg>
      )}
    </span>
  );
}

export function StudentChatAvatar() {
  const src = useActiveStudentAvatarSrc();
  return <StudentAvatarMark src={src} size={40} />;
}
