import { redirect } from "next/navigation";

import { STUDENT_HOME } from "@/lib/student-routes";

/** 舊書籤 /dashboard → 學生首頁 /home */
export default function DashboardLegacyRedirect() {
  redirect(STUDENT_HOME);
}
