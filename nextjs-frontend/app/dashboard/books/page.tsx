import { AssessmentEbookCard } from "@/components/orid/AssessmentEbookCard";
import { DashboardWeekGrid } from "@/components/orid/DashboardWeekGrid";
import { DemoPracticeSection } from "@/components/orid/DemoPracticeSection";

export default function BooksPage() {
  return (
    <div className="flex flex-col gap-4 pb-6">
      <DemoPracticeSection />

      <section aria-label="前測閱讀">
        <h2 className="mb-3 text-base font-bold text-amber-950 sm:text-lg">前測</h2>
        <AssessmentEbookCard kind="pre" />
      </section>

      <div>
        <h1 className="text-xl font-bold text-amber-950 sm:text-2xl">每週閱讀</h1>
        <p className="mt-1 text-sm text-amber-800/60 sm:text-base">
          三本書分成七週。已開放的週次可以直接點進去喔！
        </p>
      </div>

      <DashboardWeekGrid />

      <section aria-label="後測閱讀">
        <h2 className="mb-3 text-base font-bold text-amber-950 sm:text-lg">後測</h2>
        <AssessmentEbookCard kind="post" />
      </section>
    </div>
  );
}
