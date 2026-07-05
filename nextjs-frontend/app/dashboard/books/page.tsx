import { DashboardWeekGrid } from "@/components/orid/DashboardWeekGrid";

export default function BooksPage() {
  return (
    <div className="flex flex-col gap-4 pb-6">
      <div>
        <h1 className="text-xl font-bold text-amber-950 sm:text-2xl">每週閱讀</h1>
        <p className="mt-1 text-sm text-amber-800/60 sm:text-base">
          每週一本故事書，搭配 ORID 對話與反思寫作。已開放的週次可以直接點進去喔！
        </p>
      </div>

      <DashboardWeekGrid />
    </div>
  );
}
