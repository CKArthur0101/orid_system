"use client";

import { LogOut } from "lucide-react";
import { logout } from "@/components/actions/logout-action";

export default function TeacherLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b bg-white px-6 shadow-sm">
        <div className="flex items-center gap-3">
          <span className="text-lg font-bold text-blue-600">AI–ORID</span>
          <span className="text-sm text-muted-foreground">教師儀表板</span>
        </div>
        <button
          onClick={() => logout()}
          className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm text-muted-foreground hover:bg-slate-100 hover:text-red-600 transition"
        >
          <LogOut className="h-4 w-4" />
          登出
        </button>
      </header>
      <main>{children}</main>
    </div>
  );
}
