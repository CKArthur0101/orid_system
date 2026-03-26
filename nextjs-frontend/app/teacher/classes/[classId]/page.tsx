"use client";

import Link from "next/link";
import { use, useEffect, useMemo, useState } from "react";

type OverviewRow = {
  student_id: string;
  student_email: string;
  current_stage: string;
  interaction_count: number;
  writing_completed_stages: number;
};

type Overview = {
  class_id: string;
  class_name: string;
  week: number;
  total_students: number;
  active_students: number;
  completion_rate: number;
  stage_distribution: Record<string, number>;
  students: OverviewRow[];
};

export default function TeacherClassOverviewPage({ params }: { params: Promise<{ classId: string }> }) {
  const { classId } = use(params);
  const [week, setWeek] = useState(1);
  const [data, setData] = useState<Overview | null>(null);

  useEffect(() => {
    void (async () => {
      const res = await fetch(`/api/teacher/classes/${classId}/overview?week=${week}`, {
        method: "GET",
        cache: "no-store",
      });
      if (!res.ok) return;
      const obj = await res.json().catch(() => null);
      setData(obj);
    })();
  }, [classId, week]);

  const completionPct = useMemo(() => Math.round((data?.completion_rate ?? 0) * 100), [data?.completion_rate]);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">班級概覽</h1>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">週次</span>
          <select
            value={week}
            onChange={(e) => setWeek(Number(e.target.value))}
            className="rounded border bg-white px-2 py-1 text-sm"
          >
            {[1, 2, 3, 4, 5, 6].map((w) => (
              <option key={w} value={w}>
                {w}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="mt-2 text-sm text-muted-foreground">{data?.class_name ?? "載入中..."}</div>

      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-4">
        <div className="rounded border bg-white p-3">學生數：{data?.total_students ?? 0}</div>
        <div className="rounded border bg-white p-3">活躍數：{data?.active_students ?? 0}</div>
        <div className="rounded border bg-white p-3">完成率：{completionPct}%</div>
        <div className="rounded border bg-white p-3">
          階段分布：O {data?.stage_distribution?.O ?? 0} / R {data?.stage_distribution?.R ?? 0} / I{" "}
          {data?.stage_distribution?.I ?? 0} / D {data?.stage_distribution?.D ?? 0}
        </div>
      </div>

      <div className="mt-5 overflow-auto rounded border bg-white">
        <table className="w-full text-sm">
          <thead className="bg-muted/40">
            <tr>
              <th className="p-2 text-left">學生</th>
              <th className="p-2 text-left">目前階段</th>
              <th className="p-2 text-left">互動次數</th>
              <th className="p-2 text-left">寫作完成段數</th>
              <th className="p-2 text-left">操作</th>
            </tr>
          </thead>
          <tbody>
            {(data?.students ?? []).map((row) => (
              <tr key={row.student_id} className="border-t">
                <td className="p-2">{row.student_email}</td>
                <td className="p-2">{row.current_stage}</td>
                <td className="p-2">{row.interaction_count}</td>
                <td className="p-2">{row.writing_completed_stages}</td>
                <td className="p-2">
                  <Link
                    className="rounded border px-2 py-1 hover:bg-muted"
                    href={`/teacher/classes/${classId}/students/${row.student_id}?week=${week}`}
                  >
                    查看
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
