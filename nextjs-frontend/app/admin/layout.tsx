"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { LogOut } from "lucide-react";

import { logoutToLogin } from "@/lib/logout";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/admin/users", label: "使用者" },
  { href: "/admin/classes", label: "班級" },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [greeting, setGreeting] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const r = await fetch("/api/users/me", { credentials: "include", cache: "no-store" });
        if (!r.ok || cancelled) return;
        const u = await r.json().catch(() => null);
        if (!u || cancelled) return;
        const name = String(u.display_name ?? u.email ?? "").trim();
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
        <div className="mx-auto flex h-14 max-w-[1200px] items-center justify-between px-4 sm:px-6">
          <div className="flex items-center gap-4">
            <span className="text-lg font-bold text-blue-600">AI–ORID 管理</span>
            <nav className="flex gap-1">
              {NAV.map(({ href, label }) => (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "rounded-md px-3 py-1.5 text-sm font-medium transition",
                    pathname?.startsWith(href)
                      ? "bg-blue-50 text-blue-700"
                      : "text-slate-600 hover:bg-slate-100",
                  )}
                >
                  {label}
                </Link>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-2">
            {greeting && (
              <span className="hidden max-w-[12rem] truncate text-sm text-slate-500 sm:inline">
                {greeting}
              </span>
            )}
            <button
              type="button"
              onClick={() => void logoutToLogin()}
              className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100 hover:text-red-600"
            >
              <LogOut className="h-4 w-4" />
              登出
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1200px] px-4 py-6 sm:px-6">{children}</main>
    </div>
  );
}
