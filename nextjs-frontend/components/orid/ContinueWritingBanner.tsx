"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ORID_UNLOCKED_WEEKS } from "@/lib/orid-week-access";

interface ProgressData {
  earnedBadges: string[];
  totalScore: number | null;
}

async function fetchWeekProgress(week: number): Promise<ProgressData | null> {
  try {
    // Ensure a session exists for this week (idempotent: returns existing session if any)
    const sessionRes = await fetch(`/api/orid/sessions/ensure?week=${week}`, {
      method: "POST",
      cache: "no-store",
    });
    if (!sessionRes.ok) return null;
    const session = await sessionRes.json();
    const sessionId: string | undefined = session?.id;
    if (!sessionId) return null;

    const progressRes = await fetch(
      `/api/orid/progress?session_id=${sessionId}&week=${week}`,
      { cache: "no-store" }
    );
    if (!progressRes.ok) return null;
    return await progressRes.json();
  } catch {
    return null;
  }
}

export function ContinueWritingBanner() {
  const [entry, setEntry] = useState<{
    week: number;
    progress: ProgressData;
  } | null | "loading">("loading");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      for (let w = ORID_UNLOCKED_WEEKS; w >= 1; w--) {
        if (cancelled) return;
        const data = await fetchWeekProgress(w);
        if (cancelled) return;
        if (data && ((data.totalScore ?? 0) > 0 || data.earnedBadges.length > 0)) {
          setEntry({ week: w, progress: data });
          return;
        }
      }
      if (!cancelled) setEntry(null);
    })();
    return () => { cancelled = true; };
  }, []);

  if (entry === "loading" || entry === null) return null;

  const { week, progress } = entry;
  const score = progress.totalScore ?? 0;
  const badges = progress.earnedBadges.length;

  return (
    <Link href={`/dashboard/books/week/${week}`}>
      <div className="kid-shell flex items-center gap-3 px-4 py-3 transition-all hover:shadow-lg hover:scale-[1.005] active:scale-[0.995] cursor-pointer sm:gap-4 sm:px-5 sm:py-4">
        <div className="h-12 w-1 shrink-0 rounded-full bg-gradient-to-b from-amber-500 to-orange-600" />

        <div className="flex-1 min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-600">
            繼續上次的寫作
          </p>
          <p className="mt-0.5 text-sm font-bold text-amber-950 sm:text-base">
            第 {week} 週
          </p>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            {score > 0 && (
              <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-bold text-amber-900">
                {score} / 90
              </span>
            )}
            {badges > 0 && (
              <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-bold text-emerald-800">
                🏅 × {badges}
              </span>
            )}
          </div>
        </div>

        <span className="shrink-0 text-xl text-amber-500" aria-hidden>→</span>
      </div>
    </Link>
  );
}
