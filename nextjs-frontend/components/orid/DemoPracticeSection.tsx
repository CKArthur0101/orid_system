"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { WeekSelectionCard } from "@/components/orid/WeekSelectionCard";
import { ORID_DEMO_WEEK_OPEN, oridWeekIsAccessible } from "@/lib/orid-week-access";
import { getWeekBookMeta, DASHBOARD_ART } from "@/lib/orid-system-art";
import { getBookWeekArt } from "@/lib/orid-book-art";
import { DEMO_WEEK } from "@/lib/orid/week-flow";

interface WeekProgress {
  earnedBadges: string[];
  encouragement?: boolean;
}

async function fetchWeekProgress(week: number): Promise<WeekProgress | null> {
  try {
    const sessionRes = await fetch(`/api/orid/sessions/ensure?week=${week}`, {
      method: "POST",
      cache: "no-store",
    });
    if (!sessionRes.ok) return null;
    const session = await sessionRes.json();
    const sessionId: string | undefined = session?.id;
    if (!sessionId) return null;
    const condition = String(session?.condition ?? "").trim().toLowerCase();

    const r = await fetch(`/api/orid/progress?session_id=${sessionId}&week=${week}`, {
      cache: "no-store",
    });
    if (!r.ok) return null;
    const progress = await r.json();
    return {
      ...progress,
      encouragement: condition === "control" || condition === "template",
    };
  } catch {
    return null;
  }
}

export function DemoPracticeSection() {
  const [progress, setProgress] = useState<WeekProgress | null>(null);

  useEffect(() => {
    if (!ORID_DEMO_WEEK_OPEN || !oridWeekIsAccessible(DEMO_WEEK)) return;
    fetchWeekProgress(DEMO_WEEK).then((data) => {
      if (data) setProgress(data);
    });
  }, []);

  if (!ORID_DEMO_WEEK_OPEN) return null;

  const demoMeta = getWeekBookMeta(DEMO_WEEK);
  const demoArt = getBookWeekArt(DEMO_WEEK);

  return (
    <section aria-label="系統練習">
      <h2 className="mb-3 flex items-center gap-2.5 text-base font-bold text-amber-950 sm:text-lg">
        <Image
          src={DASHBOARD_ART.weeklyReadingIcon}
          alt=""
          width={40}
          height={40}
          className="h-9 w-9 shrink-0 object-contain drop-shadow-sm sm:h-10 sm:w-10"
          aria-hidden
        />
        系統練習（說明用）
      </h2>
      <ul className="grid list-none grid-cols-1 gap-3 p-0 md:grid-cols-2 md:gap-4 md:max-w-[calc(66.666%-0.34rem)] lg:max-w-[calc(66.666%-0.42rem)] lg:gap-5">
        <li className="min-h-[148px]">
          <WeekSelectionCard
            week={DEMO_WEEK}
            title={demoArt?.title ?? demoMeta.title}
            subtitle={demoMeta.subtitle ?? "先熟悉寫作與回饋怎麼用"}
            coverThumb={demoArt?.coverThumb ?? demoMeta.coverThumb}
            locked={!oridWeekIsAccessible(DEMO_WEEK)}
            earnedBadges={progress?.earnedBadges}
            encouragement={progress?.encouragement}
          />
        </li>
      </ul>
    </section>
  );
}
