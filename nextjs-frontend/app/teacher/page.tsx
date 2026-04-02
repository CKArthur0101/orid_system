"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Users,
  Activity,
  CheckCircle2,
  BarChart3,
  ChevronRight,
  MessageSquare,
  FileText,
  Clock,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type ClassInfo = {
  id: string;
  name: string;
  year: number;
  external_code: string | null;
};
type StudentRow = {
  student_id: string;
  student_email: string;
  current_stage: string;
  interaction_count: number;
  writing_completed_stages: number;
  last_activity_at: string | null;
};
type Overview = {
  class_id: string;
  class_name: string;
  week: number;
  total_students: number;
  active_students: number;
  completion_rate: number;
  stage_distribution: Record<string, number>;
  students: StudentRow[];
};
type StudentSummary = {
  class_id: string;
  student_id: string;
  student_email: string;
  week: number;
  current_stage: string;
  interaction_count: number;
  writing_completed_stages: number;
  last_activity_at: string | null;
};

const STAGE_COLORS: Record<string, string> = {
  O: "#3b82f6",
  R: "#f59e0b",
  I: "#8b5cf6",
  D: "#10b981",
};
const STAGE_LABELS: Record<string, string> = {
  O: "客觀 (O)",
  R: "感受 (R)",
  I: "意義 (I)",
  D: "行動 (D)",
};
const WEEKS = [1, 2, 3, 4, 5, 6];

export default function TeacherDashboardPage() {
  const [classes, setClasses] = useState<ClassInfo[]>([]);
  const [classId, setClassId] = useState("");
  const [week, setWeek] = useState(1);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(true);

  const [selectedStudentId, setSelectedStudentId] = useState("");
  const [studentDetail, setStudentDetail] = useState<StudentSummary | null>(null);

  // On mount: fetch classes then immediately fetch overview with the first class
  useEffect(() => {
    void (async () => {
      setLoading(true);
      const res = await fetch("/api/teacher/me/classes", { cache: "no-store" });
      if (!res.ok) { setLoading(false); return; }
      const list: ClassInfo[] = await res.json().catch(() => []);
      setClasses(list);
      if (!list.length) { setLoading(false); return; }

      const firstId = list[0].id;
      setClassId(firstId);

      // Immediately fetch overview without waiting for a second render cycle
      const oRes = await fetch(`/api/teacher/classes/${firstId}/overview?week=1`, {
        cache: "no-store",
      });
      if (oRes.ok) {
        const data: Overview = await oRes.json().catch(() => null);
        setOverview(data);
        if (data?.students?.length) setSelectedStudentId(data.students[0].student_id);
      }
      setLoading(false);
    })();
  }, []);

  // Re-fetch overview when classId or week changes (but not on the initial mount handled above)
  useEffect(() => {
    if (!classId) return;
    setLoading(true);
    void (async () => {
      const res = await fetch(`/api/teacher/classes/${classId}/overview?week=${week}`, {
        cache: "no-store",
      });
      if (res.ok) {
        const data: Overview = await res.json().catch(() => null);
        setOverview(data);
        if (data?.students?.length && !selectedStudentId) {
          setSelectedStudentId(data.students[0].student_id);
        }
      }
      setLoading(false);
    })();
  }, [classId, week]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!classId || !selectedStudentId) return;
    void (async () => {
      const res = await fetch(
        `/api/teacher/classes/${classId}/student-summary?studentId=${selectedStudentId}&week=${week}`,
        { cache: "no-store" }
      );
      if (res.ok) setStudentDetail(await res.json().catch(() => null));
    })();
  }, [classId, selectedStudentId, week]);

  const completionPct = useMemo(
    () => Math.round((overview?.completion_rate ?? 0) * 100),
    [overview?.completion_rate]
  );
  const avgInteractions = useMemo(() => {
    if (!overview?.students?.length) return 0;
    const total = overview.students.reduce((s, r) => s + r.interaction_count, 0);
    return +(total / overview.students.length).toFixed(1);
  }, [overview?.students]);

  const stageDist = overview?.stage_distribution ?? { O: 0, R: 0, I: 0, D: 0 };
  const stageTotal = Object.values(stageDist).reduce((a, b) => a + b, 0) || 1;

  const className = classes.find((c) => c.id === classId)?.name ?? "";

  const selectedStudent = overview?.students?.find((s) => s.student_id === selectedStudentId);

  return (
    <div className="mx-auto max-w-[1400px] p-6">
      {/* Top controls */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-slate-800">
          AI–ORID 教師儀表板
        </h1>
        <div className="flex items-center gap-3">
          <Select value={classId} onValueChange={setClassId}>
            <SelectTrigger className="w-[200px] bg-white">
              <SelectValue placeholder="選擇班級" />
            </SelectTrigger>
            <SelectContent>
              {classes.map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  {c.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={String(week)} onValueChange={(v) => setWeek(Number(v))}>
            <SelectTrigger className="w-[100px] bg-white">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {WEEKS.map((w) => (
                <SelectItem key={w} value={String(w)}>
                  第 {w} 週
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {loading ? (
        <div className="flex h-64 items-center justify-center text-muted-foreground">
          載入中...
        </div>
      ) : (
        <Tabs defaultValue="overview" className="space-y-6">
          <TabsList className="grid w-full max-w-md grid-cols-2 bg-blue-50">
            <TabsTrigger
              value="overview"
              className="data-[state=active]:bg-blue-600 data-[state=active]:text-white"
            >
              班級概覽
            </TabsTrigger>
            <TabsTrigger
              value="tracking"
              className="data-[state=active]:bg-blue-600 data-[state=active]:text-white"
            >
              個人追蹤
            </TabsTrigger>
          </TabsList>

          {/* ===== TAB: 班級概覽 ===== */}
          <TabsContent value="overview" className="space-y-6">
            {/* Stats row */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard
                icon={<Users className="h-5 w-5 text-blue-600" />}
                label="學生人數"
                value={overview?.total_students ?? 0}
                sub={`${overview?.active_students ?? 0} 人活躍`}
              />
              <StatCard
                icon={<CheckCircle2 className="h-5 w-5 text-emerald-600" />}
                label="整體完成率"
                value={`${completionPct}%`}
                sub="四階段皆完成"
              />
              <StatCard
                icon={<MessageSquare className="h-5 w-5 text-amber-600" />}
                label="平均互動回合"
                value={avgInteractions}
                sub="每位學生平均"
              />
              <StatCard
                icon={<Activity className="h-5 w-5 text-purple-600" />}
                label="班級平均完成"
                value={`${className}`}
                sub={`第 ${week} 週`}
              />
            </div>

            {/* Charts row */}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              {/* ORID Stage Distribution */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <BarChart3 className="h-4 w-4 text-blue-600" />
                    ORID 階段參與分布
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {(["O", "R", "I", "D"] as const).map((stage) => {
                      const count = stageDist[stage] ?? 0;
                      const pct = Math.round((count / stageTotal) * 100);
                      return (
                        <div key={stage} className="space-y-1">
                          <div className="flex items-center justify-between text-sm">
                            <span className="font-medium">{STAGE_LABELS[stage]}</span>
                            <span className="text-muted-foreground">
                              {count} 人 ({pct}%)
                            </span>
                          </div>
                          <div className="h-3 overflow-hidden rounded-full bg-slate-100">
                            <div
                              className="h-full rounded-full transition-all duration-500"
                              style={{
                                width: `${pct}%`,
                                backgroundColor: STAGE_COLORS[stage],
                              }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  {/* Mini donut */}
                  <div className="mt-4 flex items-center justify-center gap-6">
                    <StagePie dist={stageDist} total={stageTotal} />
                    <div className="space-y-1 text-xs">
                      {(["O", "R", "I", "D"] as const).map((s) => (
                        <div key={s} className="flex items-center gap-1.5">
                          <span
                            className="inline-block h-2.5 w-2.5 rounded-full"
                            style={{ backgroundColor: STAGE_COLORS[s] }}
                          />
                          {STAGE_LABELS[s]}
                        </div>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Student list */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <FileText className="h-4 w-4 text-blue-600" />
                    學生清單
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  <div className="max-h-[360px] overflow-auto">
                    <table className="w-full text-sm">
                      <thead className="sticky top-0 bg-slate-50">
                        <tr className="text-left text-muted-foreground">
                          <th className="px-4 py-2.5">學生</th>
                          <th className="px-4 py-2.5">階段</th>
                          <th className="px-4 py-2.5 text-center">完成度</th>
                          <th className="px-4 py-2.5 text-center">狀態</th>
                          <th className="w-8" />
                        </tr>
                      </thead>
                      <tbody>
                        {(overview?.students ?? []).map((row) => {
                          const pct = Math.round((row.writing_completed_stages / 4) * 100);
                          const needsAttention = row.interaction_count === 0;
                          return (
                            <tr
                              key={row.student_id}
                              className="border-t hover:bg-blue-50/40 cursor-pointer transition"
                              onClick={() => {
                                setSelectedStudentId(row.student_id);
                                const tabBtn = document.querySelector<HTMLButtonElement>(
                                  '[data-state][value="tracking"]'
                                );
                                tabBtn?.click();
                              }}
                            >
                              <td className="px-4 py-2.5 font-medium">
                                {row.student_email.split("@")[0]}
                              </td>
                              <td className="px-4 py-2.5">
                                <span
                                  className="inline-block rounded-full px-2 py-0.5 text-xs font-semibold text-white"
                                  style={{ backgroundColor: STAGE_COLORS[row.current_stage] ?? "#94a3b8" }}
                                >
                                  {row.current_stage}
                                </span>
                              </td>
                              <td className="px-4 py-2.5">
                                <div className="flex items-center gap-2">
                                  <div className="h-2 flex-1 rounded-full bg-slate-100">
                                    <div
                                      className="h-full rounded-full bg-blue-500 transition-all"
                                      style={{ width: `${pct}%` }}
                                    />
                                  </div>
                                  <span className="w-8 text-right text-xs text-muted-foreground">
                                    {pct}%
                                  </span>
                                </div>
                              </td>
                              <td className="px-4 py-2.5 text-center">
                                {needsAttention ? (
                                  <span className="text-xs text-orange-500 font-medium">
                                    需關注
                                  </span>
                                ) : (
                                  <span className="text-xs text-emerald-600">正常</span>
                                )}
                              </td>
                              <td className="pr-3">
                                <ChevronRight className="h-4 w-4 text-muted-foreground" />
                              </td>
                            </tr>
                          );
                        })}
                        {!(overview?.students?.length) && (
                          <tr>
                            <td colSpan={5} className="p-8 text-center text-muted-foreground">
                              尚無學生資料
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* ===== TAB: 個人追蹤 ===== */}
          <TabsContent value="tracking" className="space-y-6">
            <div className="flex flex-wrap items-center gap-4">
              <span className="text-sm font-medium text-slate-600">選擇學生：</span>
              <Select value={selectedStudentId} onValueChange={setSelectedStudentId}>
                <SelectTrigger className="w-[280px] bg-white">
                  <SelectValue placeholder="選擇學生" />
                </SelectTrigger>
                <SelectContent>
                  {(overview?.students ?? []).map((s) => (
                    <SelectItem key={s.student_id} value={s.student_id}>
                      {s.student_email}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {studentDetail ? (
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                {/* Left: ORID completion */}
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base">ORID 完成狀態</CardTitle>
                    <p className="text-sm text-muted-foreground">
                      {studentDetail.student_email} — 第 {studentDetail.week} 週
                    </p>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {(["O", "R", "I", "D"] as const).map((stage) => {
                      const stageIdx = ["O", "R", "I", "D"].indexOf(stage);
                      const currentIdx = ["O", "R", "I", "D"].indexOf(
                        studentDetail.current_stage || "O"
                      );
                      const completed = stageIdx < currentIdx;
                      const current = stageIdx === currentIdx;
                      const pct = completed ? 100 : current ? 50 : 0;
                      return (
                        <div key={stage} className="space-y-1.5">
                          <div className="flex items-center justify-between text-sm">
                            <span className="font-medium">{STAGE_LABELS[stage]}</span>
                            <span className="text-muted-foreground">
                              {completed ? "已完成" : current ? "進行中" : "未開始"}
                            </span>
                          </div>
                          <div className="h-4 overflow-hidden rounded-full bg-slate-100">
                            <div
                              className="h-full rounded-full transition-all duration-700"
                              style={{
                                width: `${pct}%`,
                                backgroundColor: STAGE_COLORS[stage],
                                opacity: pct === 0 ? 0 : 1,
                              }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </CardContent>
                </Card>

                {/* Right: Stats + feedback */}
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <Card>
                      <CardContent className="flex items-center gap-3 p-4">
                        <div className="rounded-lg bg-blue-50 p-2">
                          <MessageSquare className="h-5 w-5 text-blue-600" />
                        </div>
                        <div>
                          <p className="text-2xl font-bold">{studentDetail.interaction_count}</p>
                          <p className="text-xs text-muted-foreground">互動次數</p>
                        </div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="flex items-center gap-3 p-4">
                        <div className="rounded-lg bg-emerald-50 p-2">
                          <FileText className="h-5 w-5 text-emerald-600" />
                        </div>
                        <div>
                          <p className="text-2xl font-bold">
                            {studentDetail.writing_completed_stages}/4
                          </p>
                          <p className="text-xs text-muted-foreground">寫作完成</p>
                        </div>
                      </CardContent>
                    </Card>
                  </div>

                  <Card>
                    <CardContent className="flex items-center gap-3 p-4">
                      <div className="rounded-lg bg-purple-50 p-2">
                        <Clock className="h-5 w-5 text-purple-600" />
                      </div>
                      <div>
                        <p className="text-sm font-medium">最後活動</p>
                        <p className="text-sm text-muted-foreground">
                          {studentDetail.last_activity_at
                            ? new Date(studentDetail.last_activity_at).toLocaleString("zh-TW")
                            : "尚無紀錄"}
                        </p>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="flex items-center gap-2 text-base">
                        💡 教學回饋建議
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <TeachingTips student={studentDetail} selectedStudent={selectedStudent} />
                    </CardContent>
                  </Card>
                </div>
              </div>
            ) : (
              <div className="flex h-48 items-center justify-center text-muted-foreground">
                請選擇一位學生
              </div>
            )}
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  sub,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  sub: string;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <div className="rounded-xl bg-slate-50 p-3">{icon}</div>
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="text-2xl font-bold">{value}</p>
          <p className="text-xs text-muted-foreground">{sub}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function StagePie({
  dist,
  total,
}: {
  dist: Record<string, number>;
  total: number;
}) {
  const stages = ["O", "R", "I", "D"];
  let cum = 0;
  const slices = stages.map((s) => {
    const pct = (dist[s] ?? 0) / total;
    const start = cum;
    cum += pct;
    return { stage: s, start, end: cum };
  });

  const r = 40;
  const cx = 50;
  const cy = 50;
  const toXY = (frac: number) => ({
    x: cx + r * Math.cos(2 * Math.PI * frac - Math.PI / 2),
    y: cy + r * Math.sin(2 * Math.PI * frac - Math.PI / 2),
  });

  return (
    <svg width="110" height="110" viewBox="0 0 100 100">
      {slices.map(({ stage, start, end }) => {
        if (end - start < 0.001) return null;
        const s = toXY(start);
        const e = toXY(end);
        const largeArc = end - start > 0.5 ? 1 : 0;
        return (
          <path
            key={stage}
            d={`M${cx},${cy} L${s.x},${s.y} A${r},${r} 0 ${largeArc},1 ${e.x},${e.y} Z`}
            fill={STAGE_COLORS[stage]}
            stroke="white"
            strokeWidth="1"
          />
        );
      })}
      <circle cx={cx} cy={cy} r="20" fill="white" />
      <text x={cx} y={cy + 1} textAnchor="middle" dominantBaseline="middle" className="text-[10px] font-bold fill-slate-700">
        {total}人
      </text>
    </svg>
  );
}

function TeachingTips({
  student,
  selectedStudent,
}: {
  student: StudentSummary;
  selectedStudent?: StudentRow;
}) {
  const tips: string[] = [];

  if (student.interaction_count === 0) {
    tips.push("此學生尚未開始互動，建議個別關心並引導進入系統。");
  } else if (student.interaction_count < 3) {
    tips.push("互動次數偏低，可鼓勵學生多嘗試與 AI 對話來深化思考。");
  }

  const stageIdx = ["O", "R", "I", "D"].indexOf(student.current_stage || "O");
  if (stageIdx <= 1 && student.interaction_count >= 5) {
    tips.push("互動次數足夠但階段停留在前期，可能遇到瓶頸，建議引導。");
  }

  if (student.writing_completed_stages === 0 && student.interaction_count > 0) {
    tips.push("已有對話互動但尚未完成任何寫作，提醒學生完成反思寫作。");
  }

  if (student.current_stage === "R") {
    tips.push("學生在感受階段，可多問「為什麼有這樣的感受？」來深化情緒表達。");
  }
  if (student.current_stage === "I") {
    tips.push("學生在意義階段，鼓勵從不同角度詮釋故事，連結自身經驗。");
  }
  if (student.current_stage === "D") {
    tips.push("學生已到行動階段，提醒設定具體可執行、可追蹤的行動計畫。");
  }

  if (student.writing_completed_stages >= 4) {
    tips.push("本週 ORID 四階段寫作已完成，表現良好！");
  }

  if (tips.length === 0) {
    tips.push("學生狀態正常，持續觀察即可。");
  }

  return (
    <ul className="space-y-2 text-sm text-slate-700">
      {tips.map((t, i) => (
        <li key={i} className="flex items-start gap-2">
          <span className="mt-0.5 inline-block h-1.5 w-1.5 rounded-full bg-blue-500 shrink-0" />
          {t}
        </li>
      ))}
    </ul>
  );
}
