import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function WeekBookPage({
  params,
}: {
  params: { week: string };
}) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">本週教材：{params.week}</h1>
        <p className="text-sm text-muted-foreground">
          這一頁之後會放：閱讀內容 + 進度條 + 聊天 + 寫作（同一個畫面）
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>📖 閱讀內容（暫時）</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          目前先用測試文字；等你給我正式教材後，我們再把 reading 內容接進來。
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>✅ 開始本週活動</CardTitle>
        </CardHeader>
        <CardContent className="flex gap-3">
          <Link
            href="/dashboard/orid-demo"
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-primary-foreground hover:opacity-90"
          >
            先到 ORID 測試頁（暫時）
          </Link>
          <Link
            href="/dashboard/books"
            className="inline-flex items-center justify-center rounded-md border px-4 py-2 hover:bg-muted"
          >
            回書籍列表
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
