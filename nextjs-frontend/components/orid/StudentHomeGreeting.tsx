"use client";

import { StudentAvatarMark, useActiveStudentAvatarSrc } from "@/components/orid/StudentAvatarMark";
import { studentHelloLine } from "@/lib/student-display-name";
import { useAuthenticatedUser } from "@/lib/use-authenticated-user";

export function StudentHomeGreeting() {
  const auth = useAuthenticatedUser("student");
  const src = useActiveStudentAvatarSrc();
  const hello = auth.status === "ready" ? studentHelloLine(auth.user) : "哈囉！";

  return (
    <div className="flex items-center gap-3">
      <StudentAvatarMark src={src} size={48} />
      <div>
        <p className="text-base font-bold text-amber-950 sm:text-lg">
          {hello}
        </p>
        <p className="text-xs text-amber-900/65 sm:text-sm">
          準備好今天的閱讀與反思了嗎？進入本週故事開始吧！
        </p>
      </div>
    </div>
  );
}
