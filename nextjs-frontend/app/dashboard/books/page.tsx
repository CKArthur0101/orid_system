import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const TOTAL_WEEKS = 6;
// 先用「目前開放到第 1 週」當測試，之後你給我實驗規則我再改成：按日期/按完成度/按研究條件解鎖
const UNLOCKED_WEEKS = 1;

export default function BooksPage() {
  const weeks = Array.from({ length: TOTAL_WEEKS }, (_, i) => i + 1);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">書籍（每週一本）</h1>
        <p className="text-sm text-muted-foreground">
          未開放的週次會先鎖住；開放後可進入聊天與寫作。
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {weeks.map((w) => {
          const locked = w > UNLOCKED_WEEKS;

          const card = (
            <Card className={locked ? "opacity-60" : "hover:shadow-md transition"}>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>第 {w} 週</span>
                  <span>{locked ? "🔒" : "✅"}</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                {locked ? "尚未開放" : "點此進入本週活動"}
              </CardContent>
            </Card>
          );

          return locked ? (
            <div key={w}>{card}</div>
          ) : (
            <Link key={w} href={`/dashboard/books/week/1`}>
              {card}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
