import Link from "next/link";

import { ORID_TOTAL_WEEKS, ORID_UNLOCKED_WEEKS } from "@/lib/orid-week-access";

const WEEK_META = [
  { icon: "🌟", color: "from-sky-400 to-sky-500", title: "第 1 週" },
  { icon: "🌈", color: "from-amber-400 to-orange-500", title: "第 2 週" },
  { icon: "🦋", color: "from-emerald-400 to-teal-500", title: "第 3 週" },
  { icon: "🌻", color: "from-violet-400 to-purple-500", title: "第 4 週" },
  { icon: "🎨", color: "from-rose-400 to-pink-500", title: "第 5 週" },
  { icon: "🌙", color: "from-cyan-400 to-blue-500", title: "第 6 週" },
];

export default function BooksPage() {
  const weeks = Array.from({ length: ORID_TOTAL_WEEKS }, (_, i) => i + 1);

  return (
    <div className="flex h-0 min-h-0 flex-1 flex-col gap-3">
      <div className="shrink-0">
        <h1 className="flex items-center gap-2 text-xl font-bold text-slate-700 sm:text-2xl">
          <span className="text-2xl">📚</span>
          每週閱讀
        </h1>
        <p className="mt-1.5 text-sm text-slate-500 sm:text-base">
          每週一本故事書，搭配 ORID 對話與反思寫作。已開放的週次可以直接點進去喔！
        </p>
      </div>

      {/* flex-1 + auto-rows：卡片列平均分配剩餘高度，貼齊視窗底（避免整頁捲動時仍由內層處理） */}
      <div className="grid min-h-0 h-0 flex-1 grid-cols-1 grid-rows-[repeat(6,minmax(0,1fr))] gap-3 sm:grid-cols-2 sm:grid-rows-[repeat(3,minmax(0,1fr))] lg:grid-cols-3 lg:grid-rows-[repeat(2,minmax(0,1fr))]">
        {weeks.map((w) => {
          const locked = w > ORID_UNLOCKED_WEEKS;
          const meta = WEEK_META[w - 1];

          if (locked) {
            return (
              <div
                key={w}
                className="relative flex h-full min-h-0 flex-col justify-between overflow-hidden rounded-xl border-2 border-dashed border-slate-200 bg-slate-50 p-5 opacity-60"
              >
                <div className="flex items-center justify-between">
                  <span className="text-lg font-bold text-slate-400">
                    {meta.title}
                  </span>
                  <span className="text-2xl">🔒</span>
                </div>
                <p className="mt-2 text-sm text-slate-400 sm:text-base">尚未開放，請等老師通知</p>
              </div>
            );
          }

          return (
            <Link key={w} href={`/dashboard/books/week/${w}`} className="flex h-full min-h-0">
              <div
                className={`group relative flex h-full min-h-0 flex-1 flex-col justify-between overflow-hidden rounded-xl bg-gradient-to-br ${meta.color} p-5 text-white shadow-md transition-all hover:shadow-xl hover:scale-[1.02] active:scale-[0.98] cursor-pointer`}
              >
                <div className="absolute -right-3 -top-3 text-7xl opacity-20 transition-transform group-hover:scale-110">
                  {meta.icon}
                </div>
                <div className="relative flex flex-1 flex-col justify-between">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-lg font-bold sm:text-xl">{meta.title}</span>
                    <span className="shrink-0 rounded-full bg-white/25 px-2 py-0.5 text-xs font-medium backdrop-blur-sm sm:text-sm">
                      ✅ 已開放
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-white/90 sm:text-base">
                    點這裡進入閱讀、ORID 對話與反思寫作
                  </p>
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
