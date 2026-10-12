import Image from "next/image";
import { DilabLogo } from "@/components/orid/DilabLogo";
import { DashboardWeekGrid } from "@/components/orid/DashboardWeekGrid";
import { StudentHomeGreeting } from "@/components/orid/StudentHomeGreeting";
import { DASHBOARD_ART } from "@/lib/orid-system-art";

export default function StudentHomePage() {
  return (
    <div className="orid-dashboard-page flex flex-1 flex-col gap-4 pb-6">
      <div className="kid-shell flex flex-col gap-3 px-4 py-3.5 sm:flex-row sm:items-center sm:gap-4 sm:px-5 sm:py-4">
        <DilabLogo height={40} className="self-start sm:shrink-0" />
        <StudentHomeGreeting />
      </div>

      <section>
        <h2 className="mb-3 flex items-center gap-2.5 text-base font-bold text-amber-950 sm:text-lg">
          <Image
            src={DASHBOARD_ART.weeklyReadingIcon}
            alt=""
            width={40}
            height={40}
            className="h-9 w-9 shrink-0 object-contain drop-shadow-sm sm:h-10 sm:w-10"
            aria-hidden
          />
          每週閱讀
        </h2>
        <DashboardWeekGrid />
      </section>
    </div>
  );
}
