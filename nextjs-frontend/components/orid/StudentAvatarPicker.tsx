"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { StudentAvatarMark, useActiveStudentAvatarSrc } from "@/components/orid/StudentAvatarMark";
import {
  STUDENT_AVATARS,
  activateStoredAvatar,
  readActiveAvatarId,
  saveStudentAvatar,
  studentAvatarKey,
} from "@/lib/orid/student-avatars";

export function StudentAvatarPicker({
  userKey,
  name,
}: {
  userKey: string;
  name: string;
}) {
  const src = useActiveStudentAvatarSrc();
  const [open, setOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    setSelectedId(activateStoredAvatar(userKey));
  }, [userKey]);

  function choose(id: string) {
    saveStudentAvatar(userKey, id);
    setSelectedId(id);
    setOpen(false);
  }

  const currentId = selectedId ?? readActiveAvatarId();

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex min-w-0 items-center gap-1.5 rounded-full py-1 pl-1 pr-2 text-left hover:bg-amber-100/70"
        aria-label="更換頭像"
      >
        <StudentAvatarMark src={src} size={32} />
        <span className="max-w-[9rem] truncate text-xs font-bold text-amber-950 sm:max-w-[14rem] sm:text-sm">
          {name}
        </span>
      </button>
      {open
        ? createPortal(
            <div
              className="fixed inset-0 z-[80] flex items-start justify-center overflow-y-auto bg-amber-950/30 px-4 pb-8 pt-[4.75rem]"
              onClick={() => setOpen(false)}
            >
              <div
                className="kid-shell w-full max-w-sm p-4 sm:max-w-md sm:p-5"
                role="dialog"
                aria-labelledby="student-avatar-title"
                onClick={(event) => event.stopPropagation()}
              >
                <h2 id="student-avatar-title" className="text-lg font-bold text-amber-950">
                  請選擇頭像
                </h2>
                <p className="mt-1 text-sm text-amber-900/70">選好之後，聊天室也會換成這張~</p>
                <div className="mt-4 grid grid-cols-4 justify-items-center gap-3">
                  {STUDENT_AVATARS.map((avatar) => {
                    const picked = avatar.id === currentId;
                    return (
                      <button
                        key={avatar.id}
                        type="button"
                        onClick={() => choose(avatar.id)}
                        className={`h-16 w-16 overflow-hidden rounded-full ring-2 ring-offset-2 ring-offset-[#f3e8d8] sm:h-[4.5rem] sm:w-[4.5rem] ${
                          picked ? "ring-amber-700" : "ring-transparent hover:ring-amber-300"
                        }`}
                        aria-label={avatar.label}
                        aria-pressed={picked}
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={avatar.src} alt="" className="h-full w-full object-contain" />
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>,
            document.body,
          )
        : null}
    </>
  );
}
