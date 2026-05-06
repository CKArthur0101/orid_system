"use client";

import { useEffect, useMemo, useState, useCallback } from "react";
import {
  Users,
  Activity,
  CheckCircle2,
  BarChart3,
  ChevronRight,
  MessageSquare,
  FileText,
  Clock,
  Download,
  ThumbsUp,
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

// ── Types ──────────────────────────────────────────────────────────────────────
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
  feedback_click_count: number;
  feedback_ok_count: number;
  feedback_ok_stages: number;
};

type Overview = {
  class_id: string;
  class_name: string;
  week: number;
  total_students: number;
  active_students: number;
  completion_rate: number;
  feedback_ok_rate: number;
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
  stages_with_draft: string[];
  last_activity_at: string | null;
  feedback_click_count: number;
  feedback_ok_count: number;
  feedback_ok_stages: number;
};

type PostTestScore = {
  id: string;
  student_id: string;
  week: number;
  stage: string;
  rubric_id: string | null;
  score: number;
  max_score: number;
  note: string | null;
};

type RubricLevel = { label: string; desc: string };
type RubricItem = { id: string; name: string; levels: RubricLevel[] };
type RubricByStage = Record<string, RubricItem[]>;
type WritingRubric = { schema: string; by_stage: RubricByStage } | null;

// ── Constants ──────────────────────────────────────────────────────────────────
const STAGE_COLORS: Record<string, string> = {
  NOT_STARTED: "#94a3b8",
  O: "#3b82f6",
  R: "#f59e0b",
  I: "#8b5cf6",
  D: "#10b981",
};
const STAGE_LABELS: Record<string, string> = {
  NOT_STARTED: "未開始",
  O: "客觀 (O)",
  R: "感受 (R)",
  I: "意義 (I)",
  D: "行動 (D)",
};
const DISPLAY_STAGES = ["NOT_STARTED", "O", "R", "I", "D"] as const;
const ORID_STAGES = ["O", "R", "I", "D"] as const;
const WEEKS = [1, 2, 3, 4, 5, 6];
const POST_TEST_STAGES = ["O", "R", "I", "D", "ALL"];

// ── Main page ──────────────────────────────────────────────────────────────────
export default function TeacherDashboardPage() {
  const [classes, setClasses] = useState<ClassInfo[]>([]);
  const [classId, setClassId] = useState("");
  const [week, setWeek] = useState(1);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedStudentId, setSelectedStudentId] = useState("");
  const [detailLoading, setDetailLoading] = useState(false);
  const [studentDetail, setStudentDetail] = useState<StudentSummary | null>(null);
  const [postTestScores, setPostTestScores] = useState<PostTestScore[]>([]);
  const [ptDraft, setPtDraft] = useState<Record<string, string>>({});
  const [ptSaving, setPtSaving] = useState(false);
  const [writingRubric, setWritingRubric] = useState<WritingRubric>(null);
  const [rubricOpen, setRubricOpen] = useState(false);

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

  // Re-fetch overview when classId or week changes
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

  // Fetch rubric when week changes
  useEffect(() => {
    void (async () => {
      const res = await fetch(`/api/teacher/rubric?week=${week}`, { cache: "no-store" });
      if (res.ok) {
        const data = await res.json().catch(() => null);
        setWritingRubric(data?.writing_rubric ?? null);
      }
    })();
  }, [week]);

  // Fetch student detail and post-test scores when selected student changes
  useEffect(() => {
    if (!classId || !selectedStudentId) {
      setStudentDetail(null);
      setDetailLoading(false);
      return;
    }
    setDetailLoading(true);
    void (async () => {
      try {
        const [detailRes, ptRes] = await Promise.all([
          fetch(
            `/api/teacher/classes/${classId}/students/${selectedStudentId}/summary?week=${week}`,
            { cache: "no-store" },
          ),
          fetch(
            `/api/teacher/classes/${classId}/students/${selectedStudentId}/post-test?week=${week}`,
            { cache: "no-store" },
          ),
        ]);
        if (detailRes.ok) {
          const d = await detailRes.json().catch(() => null);
          setStudentDetail(d);
        } else {
          setStudentDetail(null);
        }
        if (ptRes.ok) {
          const scores: PostTestScore[] = await ptRes.json().catch(() => []);
          setPostTestScores(scores);
          const draft: Record<string, string> = {};
          for (const s of scores) draft[s.stage] = String(s.score);
          setPtDraft(draft);
        }
      } finally {
        setDetailLoading(false);
      }
    })();
  }, [classId, selectedStudentId, week]);

  const handleExport = useCallback(async () => {
    const res = await fetch(`/api/teacher/classes/${classId}/export?week=${week}`);
    if (!res.ok) return;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `class_week${week}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [classId, week]);

  const handleSavePostTest = useCallback(async () => {
    if (!selectedStudentId || !classId) return;
    setPtSaving(true);
    try {
      for (const stage of POST_TEST_STAGES) {
        const raw = ptDraft[stage];
        if (raw === undefined || raw === "") continue;
        const score = parseInt(raw, 10);
        if (isNaN(score)) continue;
        await fetch(
          `/api/teacher/classes/${classId}/students/${selectedStudentId}/post-test`,
          {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ week, stage, score, max_score: 4 }),
          }
        );
      }
      // Refresh
      const ptRes = await fetch(
        `/api/teacher/classes/${classId}/students/${selectedStudentId}/post-test?week=${week}`,
        { cache: "no-store" }
      );
      if (ptRes.ok) setPostTestScores(await ptRes.json().catch(() => []));
    } finally {
      setPtSaving(false);
    }
  }, [classId, selectedStudentId, week, ptDraft]);

  const completionPct = useMemo(
    () => Math.round((overview?.completion_rate ?? 0) * 100),
    [overview?.completion_rate]
  );
  const feedbackOkPct = useMemo(
    () => Math.round((overview?.feedback_ok_rate ?? 0) * 100),
    [overview?.feedback_ok_rate]
  );
  const avgInteractions = useMemo(() => {
    if (!overview?.students?.length) return 0;
    const total = overview.students.reduce((s, r) => s + r.interaction_count, 0);
    return +(total / overview.students.length).toFixed(1);
  }, [overview?.students]);

  const stageDist = overview?.stage_distribution ?? { NOT_STARTED: 0, O: 0, R: 0, I: 0, D: 0 };
  const stageTotal = Object.values(stageDist).reduce((a, b) => a + b, 0) || 1;
  const className = classes.find((c) => c.id === classId)?.name ?? "";
  const selectedStudent = overview?.students?.find((s) => s.student_id === selectedStudentId);

  return (
    <div className="mx-auto max-w-[1400px] p-6">
      {/* Top controls */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-slate-800 sm:text-3xl">AI–ORID 教師儀表板</h1>
        <div className="flex items-center gap-3">
          <Select value={classId} onValueChange={setClassId}>
            <SelectTrigger className="w-[200px] bg-white">
              <SelectValue placeholder="選擇班級" />
            </SelectTrigger>
            <SelectContent>
              {classes.map((c) => (
                <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={String(week)} onValueChange={(v) => setWeek(Number(v))}>
            <SelectTrigger className="w-[100px] bg-white">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {WEEKS.map((w) => (
                <SelectItem key={w} value={String(w)}>第 {w} 週</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <button
            onClick={handleExport}
            disabled={!classId}
            className="flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 py-2 text-base font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40"
          >
            <Download className="h-4 w-4" />
            匯出 CSV
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex h-64 items-center justify-center text-muted-foreground">載入中...</div>
      ) : (
        <Tabs defaultValue="overview" className="space-y-6">
          <TabsList className="grid w-full max-w-md grid-cols-2 bg-blue-50">
            <TabsTrigger value="overview" className="data-[state=active]:bg-blue-600 data-[state=active]:text-white">
              班級概覽
            </TabsTrigger>
            <TabsTrigger value="tracking" className="data-[state=active]:bg-blue-600 data-[state=active]:text-white">
              個人追蹤
            </TabsTrigger>
          </TabsList>

          {/* ===== TAB: 班級概覽 ===== */}
          <TabsContent value="overview" className="space-y-6">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard
                icon={<Users className="h-5 w-5 text-blue-600" />}
                label="學生人數"
                value={overview?.total_students ?? 0}
                sub={`${overview?.active_students ?? 0} 人活躍`}
              />
              <StatCard
                icon={<CheckCircle2 className="h-5 w-5 text-emerald-600" />}
                label="寫作完成率"
                value={`${completionPct}%`}
                sub="四格皆有內容"
              />
              <StatCard
                icon={<ThumbsUp className="h-5 w-5 text-teal-600" />}
                label="回饋通過率"
                value={`${feedbackOkPct}%`}
                sub="四格皆獲 ok 回饋"
              />
              <StatCard
                icon={<MessageSquare className="h-5 w-5 text-amber-600" />}
                label="平均互動回合"
                value={avgInteractions}
                sub={`${className} 第 ${week} 週`}
              />
            </div>

            {/* Charts row */}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <BarChart3 className="h-4 w-4 text-blue-600" />
                    ORID 階段參與分布
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {DISPLAY_STAGES.map((stage) => {
                      const count = stageDist[stage] ?? 0;
                      const pct = Math.round((count / stageTotal) * 100);
                      return (
                        <div key={stage} className="space-y-1">
                          <div className="flex items-center justify-between text-base">
                            <span className="font-medium">{STAGE_LABELS[stage]}</span>
                            <span className="text-muted-foreground">{count} 人 ({pct}%)</span>
                          </div>
                          <div className="h-3 overflow-hidden rounded-full bg-slate-100">
                            <div
                              className="h-full rounded-full transition-all duration-500"
                              style={{ width: `${pct}%`, backgroundColor: STAGE_COLORS[stage] }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <div className="mt-4 flex items-center justify-center gap-6">
                    <StagePie dist={stageDist} total={stageTotal} />
                    <div className="space-y-1 text-base">
                      {DISPLAY_STAGES.map((s) => (
                        <div key={s} className="flex items-center gap-1.5">
                          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: STAGE_COLORS[s] }} />
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
                    <table className="w-full text-base">
                      <thead className="sticky top-0 bg-slate-50">
                        <tr className="text-left text-muted-foreground">
                          <th className="px-4 py-2.5">學生</th>
                          <th className="px-4 py-2.5">階段</th>
                          <th className="px-4 py-2.5 text-center">寫作</th>
                          <th className="px-4 py-2.5 text-center">回饋 ok</th>
                          <th className="w-8" />
                        </tr>
                      </thead>
                      <tbody>
                        {(overview?.students ?? []).map((row) => {
                          const writePct = Math.round((row.writing_completed_stages / 4) * 100);
                          const okPct = Math.round((row.feedback_ok_stages / 4) * 100);
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
                                {needsAttention && (
                                  <span className="ml-1.5 text-base text-orange-500">需關注</span>
                                )}
                              </td>
                              <td className="px-4 py-2.5">
                                <span
                                  className="inline-block rounded-full px-2 py-0.5 text-base font-semibold text-white"
                                  style={{ backgroundColor: STAGE_COLORS[row.current_stage] ?? "#94a3b8" }}
                                >
                                  {row.current_stage}
                                </span>
                              </td>
                              <td className="px-4 py-2.5">
                                <MiniBar pct={writePct} color="#3b82f6" />
                              </td>
                              <td className="px-4 py-2.5">
                                <MiniBar pct={okPct} color="#10b981" />
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
              <span className="text-base font-medium text-slate-600">選擇學生：</span>
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

            {selectedStudentId && detailLoading ? (
              <div className="flex h-48 items-center justify-center text-muted-foreground">
                載入個人資料中…
              </div>
            ) : studentDetail ? (
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                {/* Left: ORID completion + feedback analytics */}
                <div className="space-y-4">
                  <Card>
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base">ORID 完成狀態</CardTitle>
                      <p className="text-base text-muted-foreground">
                        {studentDetail.student_email} — 第 {studentDetail.week} 週
                      </p>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      {ORID_STAGES.map((stage) => {
                        const isNotStarted = studentDetail.current_stage === "NOT_STARTED";
                        const stageIdx = ORID_STAGES.indexOf(stage);
                        const currentIdx = ORID_STAGES.indexOf(studentDetail.current_stage as typeof ORID_STAGES[number]);
                        const completed = stageIdx < currentIdx;
                        const isCurrent = !isNotStarted && stageIdx === currentIdx;
                        const hasDraft = (studentDetail.stages_with_draft ?? []).includes(stage);
                        // 50% only if current stage AND student has actually written something
                        const pct = completed ? 100 : (isCurrent && hasDraft) ? 50 : 0;
                        const label = completed ? "已完成"
                          : isCurrent ? (hasDraft ? "進行中" : "輪到了")
                          : "未開始";
                        return (
                          <div key={stage} className="space-y-1.5">
                            <div className="flex items-center justify-between text-base">
                              <span className="font-medium">{STAGE_LABELS[stage]}</span>
                              <span className={isCurrent && !hasDraft ? "text-amber-500 font-medium" : "text-muted-foreground"}>
                                {label}
                              </span>
                            </div>
                            <div className="h-4 overflow-hidden rounded-full bg-slate-100">
                              <div
                                className="h-full rounded-full transition-all duration-700"
                                style={{ width: `${pct}%`, backgroundColor: STAGE_COLORS[stage], opacity: pct === 0 ? 0 : 1 }}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </CardContent>
                  </Card>

                  {/* Feedback analytics */}
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="flex items-center gap-2 text-base">
                        <Activity className="h-4 w-4 text-purple-500" />
                        回饋分析
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-3 gap-3 text-center text-base">
                        <div className="rounded-lg bg-slate-50 p-3">
                          <p className="text-2xl font-bold text-slate-800">{studentDetail.feedback_click_count}</p>
                          <p className="mt-0.5 text-base text-muted-foreground">點擊次數</p>
                        </div>
                        <div className="rounded-lg bg-emerald-50 p-3">
                          <p className="text-2xl font-bold text-emerald-700">{studentDetail.feedback_ok_count}</p>
                          <p className="mt-0.5 text-base text-muted-foreground">通過次數</p>
                        </div>
                        <div className="rounded-lg bg-teal-50 p-3">
                          <p className="text-2xl font-bold text-teal-700">{studentDetail.feedback_ok_stages}/4</p>
                          <p className="mt-0.5 text-base text-muted-foreground">通過格數</p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>

                {/* Right: Stats + post-test + teaching tips */}
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <Card>
                      <CardContent className="flex items-center gap-3 p-4">
                        <div className="rounded-lg bg-blue-50 p-2">
                          <MessageSquare className="h-5 w-5 text-blue-600" />
                        </div>
                        <div>
                          <p className="text-2xl font-bold">{studentDetail.interaction_count}</p>
                          <p className="text-base text-muted-foreground">互動次數</p>
                        </div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="flex items-center gap-3 p-4">
                        <div className="rounded-lg bg-emerald-50 p-2">
                          <FileText className="h-5 w-5 text-emerald-600" />
                        </div>
                        <div>
                          <p className="text-2xl font-bold">{studentDetail.writing_completed_stages}/4</p>
                          <p className="text-base text-muted-foreground">寫作完成</p>
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
                        <p className="text-base font-medium">最後活動</p>
                        <p className="text-base text-muted-foreground">
                          {studentDetail.last_activity_at
                            ? new Date(studentDetail.last_activity_at).toLocaleString("zh-TW")
                            : "尚無紀錄"}
                        </p>
                      </div>
                    </CardContent>
                  </Card>

                  {/* Post-test score input */}
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="flex items-center justify-between gap-2 text-base">
                        <span className="flex items-center gap-2">
                          後測評分
                          <span className="text-base font-normal text-muted-foreground">（1–4 分）</span>
                        </span>
                        {writingRubric && (
                          <button
                            onClick={() => setRubricOpen((v) => !v)}
                            className="text-base font-normal text-blue-600 hover:underline"
                          >
                            {rubricOpen ? "收起評分標準" : "查看評分標準"}
                          </button>
                        )}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      {/* Rubric reference panel */}
                      {rubricOpen && writingRubric?.by_stage && (
                        <div className="mb-4 rounded-lg border border-blue-100 bg-blue-50 p-3 text-base">
                          {(["O", "R", "I", "D"] as const).map((s) => {
                            const items: RubricItem[] = writingRubric.by_stage[s] ?? [];
                            if (!items.length) return null;
                            const item = items[0];
                            return (
                              <div key={s} className="mb-2 last:mb-0">
                                <p className="mb-1 font-semibold text-slate-700">
                                  <span
                                    className="mr-1 inline-block rounded-full px-1.5 py-0.5 text-white"
                                    style={{ backgroundColor: STAGE_COLORS[s] ?? "#94a3b8", fontSize: 12 }}
                                  >
                                    {s}
                                  </span>
                                  {item.name}
                                </p>
                                <div className="space-y-0.5 pl-5">
                                  {item.levels.map((lv) => (
                                    <p key={lv.label} className="leading-snug text-slate-600">
                                      <span className="font-medium text-slate-800">{lv.label}：</span>
                                      {lv.desc}
                                    </p>
                                  ))}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                      <div className="space-y-2">
                        {POST_TEST_STAGES.map((stage) => {
                          const saved = postTestScores.find((s) => s.stage === stage);
                          return (
                            <div key={stage} className="flex items-center gap-3">
                              <span
                                className="w-8 rounded-full px-1.5 py-0.5 text-center text-base font-bold text-white"
                                style={{ backgroundColor: STAGE_COLORS[stage] ?? "#94a3b8" }}
                              >
                                {stage}
                              </span>
                              <input
                                type="number"
                                min={1}
                                max={4}
                                placeholder={saved ? String(saved.score) : "—"}
                                value={ptDraft[stage] ?? ""}
                                onChange={(e) =>
                                  setPtDraft((d) => ({ ...d, [stage]: e.target.value }))
                                }
                                className="w-20 rounded-md border border-slate-200 px-2 py-1 text-center text-base focus:border-blue-400 focus:outline-none"
                              />
                              {saved && (
                                <span className="text-base text-muted-foreground">
                                  已存：{saved.score}/{saved.max_score}
                                </span>
                              )}
                            </div>
                          );
                        })}
                      </div>
                      <button
                        onClick={handleSavePostTest}
                        disabled={ptSaving}
                        className="mt-4 w-full rounded-md bg-blue-600 py-1.5 text-base font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                      >
                        {ptSaving ? "儲存中…" : "儲存評分"}
                      </button>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="flex items-center gap-2 text-base">💡 教學回饋建議</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <TeachingTips student={studentDetail} selectedStudent={selectedStudent} />
                    </CardContent>
                  </Card>
                </div>
              </div>
            ) : selectedStudentId ? (
              <div className="flex h-48 flex-col items-center justify-center gap-2 text-center text-muted-foreground">
                <p>無法載入此學生在第 {week} 週的摘要（請檢查網路或稍後再試）。</p>
                <p className="text-xs">若剛切換週次／班級，請確認學生仍在名單中。</p>
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

// ── Sub-components ─────────────────────────────────────────────────────────────
function MiniBar({ pct, color }: { pct: number; color: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <div className="h-2 w-20 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <span className="w-8 text-right text-xs text-muted-foreground sm:text-sm">{pct}%</span>
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
      <CardContent className="flex items-center gap-4 p-4">
        <div className="rounded-xl bg-slate-50 p-2">{icon}</div>
        <div>
          <p className="text-xs text-muted-foreground sm:text-sm">{label}</p>
          <p className="text-2xl font-bold">{value}</p>
          <p className="text-xs text-muted-foreground sm:text-sm">{sub}</p>
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
  const stages = DISPLAY_STAGES;
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
      <text x={cx} y={cy + 2} textAnchor="middle" dominantBaseline="middle" className="text-[12px] font-bold fill-slate-700">
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

  const stageIdx = ORID_STAGES.indexOf(student.current_stage as typeof ORID_STAGES[number]);
  if (stageIdx <= 1 && student.interaction_count >= 5) {
    tips.push("互動次數足夠但階段停留在前期，可能遇到瓶頸，建議引導。");
  }

  if (student.writing_completed_stages === 0 && student.interaction_count > 0) {
    tips.push("已有對話互動但尚未完成任何寫作，提醒學生完成反思寫作。");
  }

  if (student.feedback_click_count > 0 && student.feedback_ok_stages < student.writing_completed_stages) {
    tips.push("學生已取得回饋但仍有格未通過，可協助檢視內容品質。");
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

  if (student.writing_completed_stages >= 4 && student.feedback_ok_stages >= 4) {
    tips.push("本週 ORID 四階段寫作與回饋皆完成，表現優異！");
  } else if (student.writing_completed_stages >= 4) {
    tips.push("四階段寫作已完成，可提醒確認每格均通過回饋評估。");
  }

  if (tips.length === 0) {
    tips.push("學生狀態正常，持續觀察即可。");
  }

  return (
    <ul className="space-y-2 text-base text-slate-700">
      {tips.map((t, i) => (
        <li key={i} className="flex items-start gap-2">
          <span className="mt-0.5 inline-block h-1.5 w-1.5 rounded-full bg-blue-500 shrink-0" />
          {t}
        </li>
      ))}
    </ul>
  );
}
