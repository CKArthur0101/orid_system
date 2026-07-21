"use client";

import { useEffect, useState } from "react";
import { WeekSelectionCard } from "@/components/orid/WeekSelectionCard";
import { ORID_TOTAL_WEEKS, ORID_UNLOCKED_WEEKS } from "@/lib/orid-week-access";
import { getWeekBookMeta } from "@/lib/orid-system-art";
import { getBookWeekArt } from "@/lib/orid-book-art";

interface WeekProgress {
  earnedBadges: string[];
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

    const r = await fetch(`/api/orid/progress?session_id=${sessionId}&week=${week}`, {
      cache: "no-store",
    });
    if (!r.ok) return null;
    return await r.json();
  } catch {
    return null;
  }
}

export function DashboardWeekGrid() {
  const weeks = Array.from({ length: ORID_TOTAL_WEEKS }, (_, i) => i + 1);
  const [progressMap, setProgressMap] = useState<Record<number, WeekProgress>>({});

  useEffect(() => {
    const accessible = weeks.filter((w) => w <= ORID_UNLOCKED_WEEKS);
    for (const w of accessible) {
      fetchWeekProgress(w).then((data) => {
        if (data) {
          setProgressMap((prev) => ({ ...prev, [w]: data }));
        }
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <ul className="grid list-none grid-cols-1 gap-4 p-0 sm:grid-cols-2 sm:gap-5 lg:grid-cols-3 lg:gap-5">
      {weeks.map((w) => {
        const locked = w > ORID_UNLOCKED_WEEKS;
        const bookArt = getBookWeekArt(w);
        const bookMeta = getWeekBookMeta(w);
        const title = bookArt?.title ?? bookMeta?.title;
        const coverThumb = bookArt?.coverThumb ?? bookMeta?.coverThumb;
        const progress = progressMap[w];

        return (
          <li key={w} className="min-h-[148px]">
            <WeekSelectionCard
              week={w}
              title={title}
              coverThumb={coverThumb}
              locked={locked}
              earnedBadges={progress?.earnedBadges}
            />
          </li>
        );
      })}
    </ul>
  );
}
