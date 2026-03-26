"use client";

import { use, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

type Summary = {
  class_id: string;
  student_id: string;
  student_email: string;
  week: number;
  current_stage: string;
  interaction_count: number;
  writing_completed_stages: number;
  last_activity_at?: string | null;
};

export default function TeacherStudentSummaryPage({
  params,
}: {
  params: Promise<{ classId: string; studentId: string }>;
}) {
  const { classId, studentId } = use(params);
  const searchParams = useSearchParams();
  const week = Number(searchParams.get("week") ?? "1") || 1;
  const [data, setData] = useState<Summary | null>(null);

  useEffect(() => {
    void (async () => {
      const res = await fetch(
        `/api/teacher/classes/${classId}/student-summary?studentId=${studentId}&week=${week}`,
        { method: "GET", cache: "no-store" }
      );
      if (!res.ok) return;
      const obj = await res.json().catch(() => null);
      setData(obj);
    })();
  }, [classId, studentId, week]);

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold">學生追蹤</h1>
      <div className="mt-2 text-sm text-muted-foreground">{data?.student_email ?? "載入中..."}</div>

      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
        <div className="rounded border bg-white p-3">週次：{data?.week ?? week}</div>
        <div className="rounded border bg-white p-3">目前階段：{data?.current_stage ?? "-"}</div>
        <div className="rounded border bg-white p-3">互動次數：{data?.interaction_count ?? 0}</div>
        <div className="rounded border bg-white p-3">寫作完成段數：{data?.writing_completed_stages ?? 0}</div>
      </div>
    </div>
  );
}
