import { redirect } from "next/navigation";

import { studentWeekPath } from "@/lib/student-routes";

type LegacyWeekPageProps = {
  params: Promise<{ week: string }>;
};

/** 舊書籤 /dashboard/books/week/:week → /week/:week */
export default async function LegacyWeekWritingRedirect({ params }: LegacyWeekPageProps) {
  const { week } = await params;
  const weekNum = Number(week);
  if (!Number.isFinite(weekNum) || weekNum < 1) {
    redirect("/home");
  }
  redirect(studentWeekPath(weekNum));
}
