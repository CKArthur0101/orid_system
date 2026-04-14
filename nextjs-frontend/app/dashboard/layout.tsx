"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen, Home, LogOut } from "lucide-react";
import { logout } from "@/components/actions/logout-action";

const NAV_ITEMS = [
  { href: "/dashboard", label: "首頁", icon: Home },
  { href: "/dashboard/books", label: "閱讀選單", icon: BookOpen },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-gradient-to-br from-sky-50 via-white to-amber-50/30">
      {/* Top navigation */}
      <header className="sticky top-0 z-30 border-b bg-white/80 backdrop-blur-md shadow-sm">
        <div className="mx-auto flex h-14 w-full max-w-[min(100vw-1.5rem,1920px)] items-center justify-between px-4 sm:px-6">
          <div className="flex items-center gap-6">
            <Link href="/dashboard" className="flex items-center gap-2">
              <span className="text-xl">📖</span>
              <span className="text-base font-bold text-sky-700">AI–ORID 反思對話</span>
            </Link>

            <nav className="hidden items-center gap-1 sm:flex">
              {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
                const active =
                  href === "/dashboard"
                    ? pathname === "/dashboard"
                    : pathname.startsWith(href);
                return (
                  <Link
                    key={href}
                    href={href}
                    className={`flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-[15px] font-medium transition ${
                      active
                        ? "bg-sky-100 text-sky-700"
                        : "text-slate-500 hover:bg-slate-100 hover:text-slate-700"
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    {label}
                  </Link>
                );
              })}
            </nav>
          </div>

          <button
            onClick={() => logout()}
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-slate-500 hover:bg-red-50 hover:text-red-600 transition"
          >
            <LogOut className="h-4 w-4" />
            <span className="hidden sm:inline">登出</span>
          </button>
        </div>
      </header>

      {/* Content */}
      <main className="mx-auto w-full max-w-[min(100vw-1.5rem,1920px)] px-4 py-4 sm:px-6 sm:py-6">
        {children}
      </main>
    </div>
  );
}
