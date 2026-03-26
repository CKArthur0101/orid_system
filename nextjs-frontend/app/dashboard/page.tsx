import Link from "next/link";

const TOTAL_WEEKS = 6;
const UNLOCKED_WEEKS = 1;

export default function DashboardPage() {
  const weeks = Array.from({ length: TOTAL_WEEKS }, (_, i) => i + 1);

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
    <div className="space-y-6">
      {/* Hero greeting */}
      <div className="rounded-2xl bg-gradient-to-r from-sky-500 to-blue-600 px-10 py-10 text-white shadow-lg sm:py-12">
        <h1 className="text-3xl font-bold sm:text-4xl">嗨！歡迎回來 👋</h1>
        <p className="mt-3 text-lg text-sky-100">
          準備好今天的閱讀與反思了嗎？選一本書開始吧！
        </p>
      </div>

      {/* Week cards */}
      <div>
        <h2 className="mb-4 flex items-center gap-2 text-xl font-bold text-slate-700">
          <span className="text-2xl">📚</span>
          每週閱讀
        </h2>

        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {weeks.map((w) => {
            const locked = w > UNLOCKED_WEEKS;

            if (locked) {
              return (
                <div
                  key={w}
                  className="relative overflow-hidden rounded-2xl border-2 border-dashed border-slate-200 bg-slate-50 p-7 opacity-60 min-h-[150px]"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xl font-bold text-slate-400">
                      第 {w} 週
                    </span>
                    <span className="text-2xl">🔒</span>
                  </div>
                  <p className="mt-3 text-base text-slate-400">尚未開放</p>
                </div>
              );
            }

            return (
              <Link key={w} href={`/dashboard/books/week/${w}`}>
                <div
                  className={`group relative overflow-hidden rounded-2xl bg-gradient-to-br ${colors[w - 1]} p-7 text-white shadow-md transition-all hover:shadow-xl hover:scale-[1.02] active:scale-[0.98] cursor-pointer min-h-[150px]`}
                >
                  <div className="absolute -right-3 -top-3 text-7xl opacity-20 transition-transform group-hover:scale-110">
                    {icons[w - 1]}
                  </div>
                  <div className="relative">
                    <div className="flex items-center justify-between">
                      <span className="text-xl font-bold">第 {w} 週</span>
                      <span className="rounded-full bg-white/25 px-3 py-1 text-sm font-medium backdrop-blur-sm">
                        可進入
                      </span>
                    </div>
                    <p className="mt-3 text-base text-white/90">
                      點這裡開始閱讀、對話與寫作
                    </p>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      </div>

      {/* How it works */}
      <div className="rounded-2xl border border-slate-200 bg-white p-8">
        <h2 className="mb-5 text-xl font-bold text-slate-700">
          🧭 這個系統怎麼使用？
        </h2>
        <div className="grid gap-5 sm:grid-cols-4">
          {[
            { step: "1", icon: "📖", title: "閱讀故事", desc: "先讀完每週的故事" },
            { step: "2", icon: "💬", title: "ORID 對話", desc: "和 AI 一起思考討論" },
            { step: "3", icon: "✍️", title: "反思寫作", desc: "用 ORID 寫下你的想法" },
            { step: "4", icon: "✅", title: "完成送出", desc: "檢查後按下儲存" },
          ].map(({ step, icon, title, desc }) => (
            <div
              key={step}
              className="flex flex-col items-center rounded-xl bg-slate-50 p-6 text-center"
            >
              <span className="text-4xl">{icon}</span>
              <span className="mt-2 text-base font-bold text-slate-700">
                {title}
              </span>
              <span className="mt-1 text-sm text-slate-500">{desc}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
