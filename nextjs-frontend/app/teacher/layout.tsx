"use client";

import { useEffect, useState } from "react";
import { LogOut } from "lucide-react";
import { logout } from "@/components/actions/logout-action";

export default function TeacherLayout({ children }: { children: React.ReactNode }) {
  const [greeting, setGreeting] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const r = await fetch("/api/users/me", { credentials: "include", cache: "no-store" });
        if (!r.ok || cancelled) return;
        const u = await r.json().catch(() => null);
        if (!u || cancelled) return;
        const loginId = String(u.email ?? "").trim();
        const name = String(u.display_name ?? "").trim() || loginId;
        setGreeting(name);
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="sticky top-0 z-30 border-b bg-white shadow-sm">
        <div className="mx-auto flex h-14 max-w-[1440px] items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <span className="text-lg font-bold text-blue-600 sm:text-xl">AI–ORID</span>
            <span className="text-sm text-muted-foreground sm:text-base">教師儀表板</span>
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            {greeting && (
              <span className="max-w-[10rem] truncate text-xs text-muted-foreground sm:max-w-[16rem] sm:text-sm">
                {greeting}
              </span>
            )}
            <button
              onClick={() => logout()}
              className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs text-muted-foreground hover:bg-slate-100 hover:text-red-600 transition sm:text-sm"
            >
              <LogOut className="h-4 w-4" />
              登出
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1440px] px-6">{children}</main>
    </div>
  );
}
