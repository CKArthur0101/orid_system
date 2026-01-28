import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default async function DashboardPage() {
  return (
    <div className="min-h-[calc(100vh-140px)] flex flex-col gap-6">
      {/* 標題區（固定高度） */}
      <div>
        <h1 className="text-2xl font-semibold">主選單</h1>
        <p className="text-sm text-muted-foreground">
          六週閱讀 × ORID 對話 × 反思寫作（研究系統）
        </p>
      </div>

      {/* 三格區：吃掉剩下高度、三張卡同高 */}
      <div className="grid flex-1 gap-6 md:grid-cols-3 items-stretch">
        <Link href="/dashboard/books" className="h-full">
          <Card className="h-full hover:shadow-md transition">
            <CardHeader>
              <CardTitle>📚 本週書籍</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              進入每週教材（依研究設定逐週開放）
            </CardContent>
          </Card>
        </Link>

        <Link href="/dashboard/orid-demo" className="h-full">
          <Card className="h-full hover:shadow-md transition">
            <CardHeader>
              <CardTitle>💬 ORID 對話（測試頁）</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              目前用來測試後端 API：reading / session / chat
            </CardContent>
          </Card>
        </Link>

        <Link href="/dashboard/progress" className="h-full">
          <Card className="h-full hover:shadow-md transition">
            <CardHeader>
              <CardTitle>📈 我的進度</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              之後會顯示：第幾週完成、ORID 階段、寫作提交狀態
            </CardContent>
          </Card>
        </Link>
      </div>
    </div>
  );
}
