"use client";

import { useEffect, useState } from "react";
import { WeekSelectionCard } from "@/components/orid/WeekSelectionCard";
import { ORID_UNLOCKED_WEEKS } from "@/lib/orid-week-access";
import { getWeekBookMeta } from "@/lib/orid-system-art";
import { getBookWeekArt } from "@/lib/orid-book-art";
import { WEEK_PLAN } from "@/lib/orid/week-flow";

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

const BOOK_UNITS = [1, 2, 3] as const;

function weeksInBook(bookUnit: number): number[] {
  return Object.values(WEEK_PLAN)
    .filter((plan) => plan.bookUnit === bookUnit)
    .map((plan) => plan.week)
    .sort((a, b) => a - b);
}

/** Two-book rows stay the same card width as the three-card row above them. */
function weekGridClass(count: number): string {
  if (count >= 3) {
    return "grid list-none grid-cols-1 gap-3 p-0 md:grid-cols-3 md:gap-4 lg:gap-5";
  }
  return "grid list-none grid-cols-1 gap-3 p-0 md:grid-cols-2 md:gap-4 md:max-w-[calc(66.666%-0.34rem)] lg:max-w-[calc(66.666%-0.42rem)] lg:gap-5";
}

export function DashboardWeekGrid() {
  const weeks = BOOK_UNITS.flatMap((unit) => weeksInBook(unit));
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
    <div className="flex flex-col gap-6 md:gap-7">
      {BOOK_UNITS.map((bookUnit) => {
        const bookWeeks = weeksInBook(bookUnit);
        const bookTitle = getBookWeekArt(bookWeeks[0])?.title ?? getWeekBookMeta(bookWeeks[0])?.title;
        const accent = getWeekBookMeta(bookWeeks[0])?.accentColor ?? "#d97706";
        return (
          <section key={bookUnit} aria-label={bookTitle ? `《${bookTitle}》` : `第 ${bookUnit} 本書`}>
            <h3 className="mb-2.5 flex items-center gap-2 text-sm font-bold text-amber-950 sm:text-base md:mb-3">
              <span
                className="inline-block h-4 w-1.5 shrink-0 rounded-full"
                style={{ backgroundColor: accent }}
                aria-hidden
              />
              {bookTitle ? `《${bookTitle}》` : "故事即將公布"}
            </h3>
            <ul className={weekGridClass(bookWeeks.length)}>
              {bookWeeks.map((w) => {
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
                      subtitle={bookMeta?.subtitle}
                      coverThumb={coverThumb}
                      locked={locked}
                      earnedBadges={progress?.earnedBadges}
                    />
                  </li>
                );
              })}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
