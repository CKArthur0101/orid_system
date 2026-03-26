import Link from "next/link";

const TOTAL_WEEKS = 6;
const UNLOCKED_WEEKS = 1;

const WEEK_META = [
  { icon: "🌟", color: "from-sky-400 to-sky-500", title: "第 1 週" },
  { icon: "🌈", color: "from-amber-400 to-orange-500", title: "第 2 週" },
  { icon: "🦋", color: "from-emerald-400 to-teal-500", title: "第 3 週" },
  { icon: "🌻", color: "from-violet-400 to-purple-500", title: "第 4 週" },
  { icon: "🎨", color: "from-rose-400 to-pink-500", title: "第 5 週" },
  { icon: "🌙", color: "from-cyan-400 to-blue-500", title: "第 6 週" },
];

export default function BooksPage() {
  const weeks = Array.from({ length: TOTAL_WEEKS }, (_, i) => i + 1);

  return (
    <div className="flex min-h-[calc(100vh-8rem)] flex-col gap-5">
      <div className="shrink-0">
        <h1 className="flex items-center gap-2 text-2xl font-bold text-slate-700">
          <span className="text-3xl">📚</span>
          每週閱讀
        </h1>
        <p className="mt-2 text-base text-slate-500">
          每週一本故事書，搭配 ORID 對話與反思寫作。已開放的週次可以直接點進去喔！
        </p>
      </div>

      <div className="grid flex-1 grid-cols-1 grid-rows-[repeat(6,1fr)] gap-5 sm:grid-cols-2 sm:grid-rows-[repeat(3,1fr)] lg:grid-cols-3 lg:grid-rows-2">
        {weeks.map((w) => {
          const locked = w > UNLOCKED_WEEKS;
          const meta = WEEK_META[w - 1];

          if (locked) {
            return (
              <div
                key={w}
                className="relative flex flex-col justify-between overflow-hidden rounded-2xl border-2 border-dashed border-slate-200 bg-slate-50 p-8 opacity-60"
              >
                <div className="flex items-center justify-between">
                  <span className="text-2xl font-bold text-slate-400">
                    {meta.title}
                  </span>
                  <span className="text-3xl">🔒</span>
                </div>
                <p className="mt-3 text-lg text-slate-400">尚未開放，請等老師通知</p>
              </div>
            );
          }

          return (
            <Link key={w} href={`/dashboard/books/week/${w}`} className="flex">
              <div
                className={`group relative flex flex-1 flex-col justify-between overflow-hidden rounded-2xl bg-gradient-to-br ${meta.color} p-8 text-white shadow-md transition-all hover:shadow-xl hover:scale-[1.02] active:scale-[0.98] cursor-pointer`}
              >
                <div className="absolute -right-4 -top-4 text-9xl opacity-20 transition-transform group-hover:scale-110">
                  {meta.icon}
                </div>
                <div className="relative flex flex-1 flex-col justify-between">
                  <div className="flex items-center justify-between">
                    <span className="text-2xl font-bold">{meta.title}</span>
                    <span className="rounded-full bg-white/25 px-4 py-1.5 text-base font-medium backdrop-blur-sm">
                      ✅ 已開放
                    </span>
                  </div>
                  <p className="mt-3 text-lg text-white/90">
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
