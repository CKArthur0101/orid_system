"use client";

import { useEffect, useState } from "react";
import { LogOut } from "lucide-react";
import { logout } from "@/components/actions/logout-action";
import { DilabLogo } from "@/components/orid/DilabLogo";
import { TeacherDashboardSideDecor } from "@/components/orid/TeacherDashboardDecor";

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
    <div className="orid-forest-page relative min-h-screen overflow-x-hidden">
      <TeacherDashboardSideDecor />

      <header className="sticky top-0 z-30 border-b border-amber-200/70 bg-[#fffcf7]/95 shadow-sm backdrop-blur-sm">
        <div className="mx-auto flex h-14 max-w-[1440px] items-center justify-between px-4 sm:px-6 md:px-10 lg:px-12">
          <div className="flex min-w-0 items-center gap-2.5 sm:gap-3">
            <DilabLogo height={28} />
            <div className="min-w-0 leading-tight">
              <span className="block text-base font-bold text-amber-950 sm:text-lg">AI–ORID</span>
              <span className="block text-[11px] text-amber-800/70 sm:text-xs">教師儀表板</span>
            </div>
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            {greeting && (
              <span className="max-w-[10rem] truncate text-xs font-medium text-amber-900/75 sm:max-w-[16rem] sm:text-sm">
                {greeting}
              </span>
            )}
            <button
              type="button"
              onClick={() => logout()}
              className="flex items-center gap-1.5 rounded-xl border border-amber-200 bg-white/80 px-3 py-1.5 text-xs font-medium text-amber-900/70 transition hover:border-amber-300 hover:bg-amber-50 hover:text-red-700 sm:text-sm"
            >
              <LogOut className="h-4 w-4" />
              登出
            </button>
          </div>
        </div>
      </header>
      {/* Tablet+: side gutters + bottom clearance so fixed mascots stay visible */}
      <main className="relative z-10 mx-auto max-w-[1440px] px-4 pb-8 sm:px-6 md:px-12 md:pb-32 lg:px-20 lg:pb-28">
        {children}
      </main>
    </div>
  );
}
