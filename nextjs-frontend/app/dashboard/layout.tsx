"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { BookOpen, ClipboardList, Home, LogOut, Map } from "lucide-react";
import { logout } from "@/components/actions/logout-action";
import { OridLogo } from "@/components/orid/OridMascotImage";

const NAV_ITEMS = [
  { href: "/dashboard", label: "首頁", icon: Home },
  { href: "/dashboard/books", label: "閱讀選單", icon: BookOpen },
  { href: "/dashboard/progress", label: "我的作品", icon: ClipboardList },
  { href: "/dashboard/progress", label: "學習歷程", icon: Map },
];

const SHELL_CLASS = "mx-auto w-full max-w-[min(100vw-1.5rem,1920px)]";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const lockWeekWritingLayout = pathname?.startsWith("/dashboard/books/week/") ?? false;
  const [greeting, setGreeting] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const r = await fetch("/api/users/me", { credentials: "include", cache: "no-store" });
        if (!r.ok || cancelled) return;
        const u = await r.json().catch(() => null);
        if (!u || cancelled) return;
        const role = String(u.role ?? "student").toLowerCase();
        const loginId = String(u.email ?? "").trim();
        const name = String(u.display_name ?? "").trim() || loginId;
        setGreeting(role === "student" ? `${name} 同學` : name);
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div
      className={`flex flex-col ${
        lockWeekWritingLayout
          ? "orid-forest-page h-dvh max-h-dvh overflow-hidden"
          : "min-h-screen min-h-dvh bg-gradient-to-br from-[#faf5eb] via-[#fffcf7] to-amber-50/40"
      }`}
    >
      <header className="sticky top-0 z-30 shrink-0 border-b border-amber-200/70 bg-[#fffcf7]/95 shadow-sm backdrop-blur-md">
        <div className={`${SHELL_CLASS} flex h-14 items-center justify-between gap-4 px-4 sm:px-6`}>
          <div className="flex min-w-0 items-center gap-4 sm:gap-6">
            <Link href="/dashboard" className="flex shrink-0 items-center gap-2">
              <OridLogo size={34} />
              <span className="text-sm font-bold text-amber-950 sm:text-base">AI–ORID 反思寫作</span>
            </Link>
            <nav className="hidden items-center gap-1 lg:flex">
              {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
                const active = href === "/dashboard" ? pathname === "/dashboard" : pathname.startsWith(href);
                return (
                  <Link
                    key={label}
                    href={href}
                    className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition ${
                      active ? "orid-nav-link-active" : "orid-nav-link"
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    {label}
                  </Link>
                );
              })}
            </nav>
          </div>
          <div className="flex shrink-0 items-center gap-2 sm:gap-3">
            {greeting ? (
              <span className="max-w-[9rem] truncate text-xs text-amber-900 sm:max-w-[14rem] sm:text-sm">🌰 {greeting}</span>
            ) : null}
            <button
              onClick={() => logout()}
              className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-amber-900/75 transition hover:bg-red-50 hover:text-red-600"
            >
              <LogOut className="h-4 w-4" />
              <span className="hidden sm:inline">登出</span>
            </button>
          </div>
        </div>
      </header>

      <main
        className={`${SHELL_CLASS} flex flex-1 flex-col px-4 py-3 sm:px-6 sm:py-4 ${
          lockWeekWritingLayout ? "min-h-0 overflow-hidden" : "min-h-0"
        }`}
      >
        {children}
      </main>
    </div>
  );
}
