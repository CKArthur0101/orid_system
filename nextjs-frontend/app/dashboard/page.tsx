import Link from "next/link";

import { ORID_TOTAL_WEEKS, ORID_UNLOCKED_WEEKS } from "@/lib/orid-week-access";

export default function DashboardPage() {
  const weeks = Array.from({ length: ORID_TOTAL_WEEKS }, (_, i) => i + 1);

  const colors = [
    "from-sky-400 to-sky-500",
    "from-amber-400 to-orange-500",
    "from-emerald-400 to-teal-500",
    "from-violet-400 to-purple-500",
    "from-rose-400 to-pink-500",
    "from-cyan-400 to-blue-500",
  ];
  const icons = ["🌟", "🌈", "🦋", "🌻", "🎨", "🌙"];

  return (
    <div className="space-y-4">
      {/* Hero greeting */}
      <div className="rounded-xl bg-gradient-to-r from-sky-500 to-blue-600 px-6 py-6 text-white shadow-lg sm:px-8 sm:py-7">
        <h1 className="text-2xl font-bold sm:text-3xl">嗨！歡迎回來 👋</h1>
        <p className="mt-2 text-base text-sky-100 sm:text-lg">
          準備好今天的閱讀與反思了嗎？選一本書開始吧！
        </p>
      </div>

      {/* Week cards */}
      <div>
        <h2 className="mb-3 flex items-center gap-2 text-lg font-bold text-slate-700 sm:text-xl">
          <span className="text-xl">📚</span>
          每週閱讀
        </h2>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {weeks.map((w) => {
            const locked = w > ORID_UNLOCKED_WEEKS;

            if (locked) {
              return (
                <div
                  key={w}
                  className="relative overflow-hidden rounded-xl border-2 border-dashed border-slate-200 bg-slate-50 p-5 opacity-60 min-h-[118px]"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-lg font-bold text-slate-400">
                      第 {w} 週
                    </span>
                    <span className="text-xl">🔒</span>
                  </div>
                  <p className="mt-2 text-sm text-slate-400 sm:text-base">
                    尚未開放，請等老師通知
                  </p>
                </div>
              );
            }

            return (
              <Link key={w} href={`/dashboard/books/week/${w}`}>
                <div
                  className={`group relative overflow-hidden rounded-xl bg-gradient-to-br ${colors[w - 1]} p-5 text-white shadow-md transition-all hover:shadow-xl hover:scale-[1.02] active:scale-[0.98] cursor-pointer min-h-[118px]`}
                >
                  <div className="absolute -right-2 -top-2 text-5xl opacity-20 transition-transform group-hover:scale-110">
                    {icons[w - 1]}
                  </div>
                  <div className="relative">
                    <div className="flex items-center justify-between">
                      <span className="text-lg font-bold">第 {w} 週</span>
                      <span className="rounded-full bg-white/25 px-2 py-0.5 text-xs font-medium backdrop-blur-sm sm:text-sm">
                        已開放
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

      {/* How it works */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 sm:p-6">
        <h2 className="mb-3 text-lg font-bold text-slate-700 sm:text-xl">
          🧭 這個系統怎麼使用？
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { step: "1", icon: "📖", title: "閱讀故事", desc: "先讀完每週的故事" },
            { step: "2", icon: "💬", title: "ORID 對話", desc: "和 AI 一起思考討論" },
            { step: "3", icon: "✍️", title: "反思寫作", desc: "用 ORID 寫下你的想法" },
            { step: "4", icon: "✅", title: "完成送出", desc: "檢查後按下儲存" },
          ].map(({ step, icon, title, desc }) => (
            <div
              key={step}
              className="flex flex-col items-center rounded-lg bg-slate-50 p-4 text-center"
            >
              <span className="text-2xl sm:text-3xl">{icon}</span>
              <span className="mt-1.5 text-sm font-bold text-slate-700 sm:text-base">
                {title}
              </span>
              <span className="mt-0.5 text-xs text-slate-500 sm:text-sm">{desc}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
