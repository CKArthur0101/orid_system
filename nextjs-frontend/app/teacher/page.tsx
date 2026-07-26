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
import { TeacherDashboardHeaderDecor } from "@/components/orid/TeacherDashboardDecor";

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
  /** 後端 TeacherStudentRow.student_display_name；無則用 student_email */
  student_display_name?: string | null;
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
  student_display_name?: string | null;
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

type OridChatLogRow = {
  id: string;
  session_id: string;
  stage: string;
  sender: string;
  text: string;
  created_at: string;
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
/** Align with student ORID stage theme (sky / amber / green / violet). */
const STAGE_COLORS: Record<string, string> = {
  NOT_STARTED: "#c4b5a0",
  O: "#6aaee0",
  R: "#e8a84d",
  I: "#66b88f",
  D: "#9f88cf",
};

const TEACHER_CARD =
  "rounded-2xl border-2 border-amber-400/45 bg-[#fffcf7]/95 shadow-md shadow-amber-950/5";
const TEACHER_SELECT =
  "rounded-xl border-amber-200 bg-[#fffcf7] text-amber-950 focus:ring-amber-400/30";
const STAGE_LABELS: Record<string, string> = {
  NOT_STARTED: "未開始",
  O: "客觀 (O)",
  R: "感受 (R)",
  I: "意義 (I)",
  D: "行動 (D)",
};
/** 班級概覽「曾動筆人數」長條順序：O～D 為有寫該段；最後一列為四段皆無內容 */
const OVERVIEW_PARTICIPATION_ORDER = ["O", "R", "I", "D", "NOT_STARTED"] as const;
function overviewParticipationLabel(stage: string): string {
  if (stage === "NOT_STARTED") return "四段皆無寫作";
  return STAGE_LABELS[stage] ?? stage;
}
const ORID_STAGES = ["O", "R", "I", "D"] as const;
const WEEKS = [1, 2, 3, 4, 5, 6];
const POST_TEST_STAGES = ["O", "R", "I", "D", "ALL"];

/** Demo：後測評分尚未完成時設 false，隱藏區塊並略過 cpt／rubric 請求 */
const SHOW_TEACHER_POST_TEST_UI = false;

function formatFastApiDetail(body: unknown): string {
  if (!body || typeof body !== "object") return "";
  const raw = (body as { detail?: unknown }).detail;
  if (typeof raw === "string") return raw;
  if (Array.isArray(raw)) {
    return raw
      .map((item) =>
        typeof item === "object" && item !== null && "msg" in item
          ? String((item as { msg: unknown }).msg)
          : JSON.stringify(item)
      )
      .filter(Boolean)
      .join("；");
  }
  return "";
}

/**
 * 最後活動時間：後端存 UTC（常為無時區字串）。無 Z／無 ±offset 時依 ISO 慣例視為 UTC 再轉成本機顯示，避免與工作列差 8 小時。
 */
function formatLastActivityLocal(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const s = String(iso).trim();
  const hasExplicitTz = /Z$/i.test(s) || /[+-]\d{2}:?\d{2}$/.test(s);
  const forParser = hasExplicitTz ? s : s.includes("T") ? `${s}Z` : s;
  const d = new Date(forParser);
  if (Number.isNaN(d.getTime())) return s;
  return d.toLocaleString("zh-TW");
}

/** 教師 BFF：對應 /api/teacher/csum 與 /api/teacher/cpt（Windows+Docker 新增 route 後若 404，請重啟 frontend 容器） */
function teacherClassStudentQs(classId: string, studentId: string, week: number) {
  return new URLSearchParams({
    classId: classId.trim(),
    studentId: studentId.trim(),
    week: String(week),
  }).toString();
}

function teacherClassStudentQsNoWeek(classId: string, studentId: string) {
  return new URLSearchParams({
    classId: classId.trim(),
    studentId: studentId.trim(),
  }).toString();
}

function studentLabel(s: { student_display_name?: string | null; student_email: string }) {
  const n = (s.student_display_name ?? "").trim();
  return n || s.student_email;
}

// ── Main page ──────────────────────────────────────────────────────────────────
export default function TeacherDashboardPage() {
  const [classes, setClasses] = useState<ClassInfo[]>([]);
  const [classId, setClassId] = useState("");
  const [week, setWeek] = useState(1);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedStudentId, setSelectedStudentId] = useState("");
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [studentDetail, setStudentDetail] = useState<StudentSummary | null>(null);
  const [postTestScores, setPostTestScores] = useState<PostTestScore[]>([]);
  const [ptDraft, setPtDraft] = useState<Record<string, string>>({});
  const [ptSaving, setPtSaving] = useState(false);
  const [writingRubric, setWritingRubric] = useState<WritingRubric>(null);
  const [rubricOpen, setRubricOpen] = useState(false);
  const [mainTab, setMainTab] = useState<"overview" | "tracking">("overview");
  const [trackingRightTab, setTrackingRightTab] = useState<"data" | "records">("data");
  const [chatMessages, setChatMessages] = useState<OridChatLogRow[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);

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
        const students = data?.students ?? [];
        // 換班級後常留下「上一個班的 student_id」，後端會 404；週次變更則沿用仍在名單內的人。
        setSelectedStudentId((prev) => {
          if (prev && students.some((s) => s.student_id === prev)) return prev;
          return students[0]?.student_id ?? "";
        });
      } else {
        // 避免沿用舊班的 student_id 對新班級發 summary → 後端 404
        setOverview(null);
        setSelectedStudentId("");
        setStudentDetail(null);
        setDetailError(null);
      }
      setLoading(false);
    })();
  }, [classId, week]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch rubric when week changes（僅後測區塊開啟時需要）
  useEffect(() => {
    if (!SHOW_TEACHER_POST_TEST_UI) {
      setWritingRubric(null);
      setRubricOpen(false);
      return;
    }
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
      setDetailError(null);
      setDetailLoading(false);
      return;
    }
    setDetailLoading(true);
    setDetailError(null);
    setPostTestScores([]);
    void (async () => {
      try {
        const qs = teacherClassStudentQs(classId, selectedStudentId, week);
        const detailRes = await fetch(`/api/teacher/csum?${qs}`, { cache: "no-store" });

        if (SHOW_TEACHER_POST_TEST_UI) {
          const ptRes = await fetch(`/api/teacher/cpt?${qs}`, { cache: "no-store" });
          if (ptRes.ok) {
            const scores: PostTestScore[] = await ptRes.json().catch(() => []);
            setPostTestScores(scores);
            const draft: Record<string, string> = {};
            for (const s of scores) draft[s.stage] = String(s.score);
            setPtDraft(draft);
          } else if (detailRes.ok) {
            const raw = await ptRes.json().catch(() => null);
            const msg = formatFastApiDetail(raw) || `後測載入 HTTP ${ptRes.status}`;
            setDetailError((prev) => (prev ? `${prev}；${msg}` : msg));
          }
        } else {
          setPostTestScores([]);
          setPtDraft({});
        }

        if (detailRes.ok) {
          const d = await detailRes.json().catch(() => null);
          setStudentDetail(d);
        } else {
          setStudentDetail(null);
          const raw = await detailRes.json().catch(() => null);
          const msg = formatFastApiDetail(raw) || `HTTP ${detailRes.status}`;
          setDetailError(msg);
        }
      } finally {
        setDetailLoading(false);
      }
    })();
  }, [classId, selectedStudentId, week]);

  useEffect(() => {
    setTrackingRightTab("data");
  }, [selectedStudentId, week]);

  useEffect(() => {
    if (!classId || !selectedStudentId || trackingRightTab !== "records") {
      if (trackingRightTab !== "records") {
        setChatMessages([]);
        setChatError(null);
        setChatLoading(false);
      }
      return;
    }
    const ac = new AbortController();
    setChatLoading(true);
    setChatError(null);
    setChatMessages([]);
    void (async () => {
      try {
        const qs = teacherClassStudentQs(classId, selectedStudentId, week);
        const res = await fetch(`/api/teacher/cchat?${qs}`, {
          cache: "no-store",
          signal: ac.signal,
        });
        if (!res.ok) {
          const raw = await res.json().catch(() => null);
          setChatError(formatFastApiDetail(raw) || `HTTP ${res.status}`);
          setChatMessages([]);
          return;
        }
        const data: unknown = await res.json().catch(() => []);
        setChatMessages(Array.isArray(data) ? (data as OridChatLogRow[]) : []);
      } catch {
        if (ac.signal.aborted) return;
        setChatError("無法載入對話紀錄");
        setChatMessages([]);
      } finally {
        if (!ac.signal.aborted) setChatLoading(false);
      }
    })();
    return () => ac.abort();
  }, [classId, selectedStudentId, week, trackingRightTab]);

  const handleSavePostTest = useCallback(async () => {
    if (!SHOW_TEACHER_POST_TEST_UI) return;
    if (!selectedStudentId || !classId) return;
    setPtSaving(true);
    try {
      for (const stage of POST_TEST_STAGES) {
        const raw = ptDraft[stage];
        if (raw === undefined || raw === "") continue;
        const score = parseInt(raw, 10);
        if (isNaN(score)) continue;
        await fetch(`/api/teacher/cpt?${teacherClassStudentQsNoWeek(classId, selectedStudentId)}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ week, stage, score, max_score: 4 }),
        });
      }
      // Refresh
      const ptRes = await fetch(
        `/api/teacher/cpt?${teacherClassStudentQs(classId, selectedStudentId, week)}`,
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
  const classTotal = overview?.total_students ?? 0;
  const denom = Math.max(classTotal, 1);
  const className = classes.find((c) => c.id === classId)?.name ?? "";
  const selectedStudent = overview?.students?.find((s) => s.student_id === selectedStudentId);
  const trackingStudentSelect = (
    <div className="flex flex-wrap items-center gap-4">
      <span className="text-base font-medium text-amber-900/75">選擇學生：</span>
      <Select
        value={selectedStudentId ? selectedStudentId : undefined}
        onValueChange={setSelectedStudentId}
      >
        <SelectTrigger className={`w-[280px] ${TEACHER_SELECT}`}>
          <SelectValue placeholder="選擇學生" />
        </SelectTrigger>
        <SelectContent className="max-h-[12.5rem]">
          {(overview?.students ?? []).map((s) => (
            <SelectItem key={s.student_id} value={s.student_id}>
              {studentLabel(s)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );

  /** 固定可捲動高度：不依賴量測左欄，避免從班級概覽切換時 flex 高度失效 */
  const recordsScrollClass =
    "min-h-[220px] max-h-[min(70vh,560px)] overflow-y-auto overscroll-contain [scrollbar-gutter:stable]";

  return (
    <div className="relative mx-auto max-w-[1400px] py-4 sm:py-6">
      {/* Top controls */}
      <div className="relative z-10 mb-6 flex flex-wrap items-center justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3 sm:gap-4">
          <div className="min-w-0">
            <h1 className="text-2xl font-bold text-amber-950 sm:text-3xl">AI–ORID 教師儀表板</h1>
            <p className="mt-0.5 text-sm text-amber-800/65">班級學習進度一覽 · 與學生系統同款暖色風格</p>
          </div>
          <TeacherDashboardHeaderDecor />
        </div>
        <div className="flex items-center gap-3">
          <Select
            value={classId}
            onValueChange={(id) => {
              setClassId(id);
              setSelectedStudentId("");
              setStudentDetail(null);
              setDetailError(null);
            }}
          >
            <SelectTrigger className={`w-[200px] ${TEACHER_SELECT}`}>
              <SelectValue placeholder="選擇班級" />
            </SelectTrigger>
            <SelectContent>
              {classes.map((c) => (
                <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={String(week)} onValueChange={(v) => setWeek(Number(v))}>
            <SelectTrigger className={`w-[100px] ${TEACHER_SELECT}`}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {WEEKS.map((w) => (
                <SelectItem key={w} value={String(w)}>第 {w} 週</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {loading ? (
        <div className="relative z-10 flex h-64 items-center justify-center text-amber-800/60">載入中...</div>
      ) : (
        <Tabs
          value={mainTab}
          onValueChange={(v) => setMainTab(v as "overview" | "tracking")}
          className="relative z-10 space-y-6"
        >
          <TabsList className="grid w-full max-w-md grid-cols-2 border border-amber-200/80 bg-amber-100/70 p-1">
            <TabsTrigger
              value="overview"
              className="rounded-lg data-[state=active]:bg-gradient-to-r data-[state=active]:from-amber-800 data-[state=active]:to-orange-900 data-[state=active]:text-amber-50 data-[state=active]:shadow-sm"
            >
              班級概覽
            </TabsTrigger>
            <TabsTrigger
              value="tracking"
              className="rounded-lg data-[state=active]:bg-gradient-to-r data-[state=active]:from-amber-800 data-[state=active]:to-orange-900 data-[state=active]:text-amber-50 data-[state=active]:shadow-sm"
            >
              個人追蹤
            </TabsTrigger>
          </TabsList>

          {/* ===== TAB: 班級概覽 ===== */}
          <TabsContent value="overview" className="space-y-6">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard
                icon={<Users className="h-5 w-5 text-[#3d7eb0]" />}
                iconBg="bg-[#eef6fc]"
                label="學生人數"
                value={overview?.total_students ?? 0}
                sub={`${overview?.active_students ?? 0} 人活躍`}
              />
              <StatCard
                icon={<CheckCircle2 className="h-5 w-5 text-[#3d8a63]" />}
                iconBg="bg-[#edf7f1]"
                label="寫作完成率"
                value={`${completionPct}%`}
                sub="四格皆有內容"
              />
              <StatCard
                icon={<ThumbsUp className="h-5 w-5 text-[#b8741f]" />}
                iconBg="bg-[#fdf5e8]"
                label="回饋通過率"
                value={`${feedbackOkPct}%`}
                sub="四格皆獲 ok 回饋"
              />
              <StatCard
                icon={<MessageSquare className="h-5 w-5 text-[#6f58a8]" />}
                iconBg="bg-[#f3effa]"
                label="平均對話輪數"
                value={avgInteractions}
                sub={`${className} 第 ${week} 週`}
              />
            </div>

            {/* Charts row */}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <Card className={TEACHER_CARD}>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-base text-amber-950">
                    <BarChart3 className="h-4 w-4 text-amber-700" />
                    ORID 階段參與（曾動筆人數）
                  </CardTitle>
                  <p className="text-sm text-amber-800/60">
                    O～D 各列為有多少人「寫過該段」，可與總人數重疊；寫齊四段會同時反映在四列。與「學生清單／目前階段」游標無關。
                  </p>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {OVERVIEW_PARTICIPATION_ORDER.map((stage) => {
                      const count = stageDist[stage] ?? 0;
                      const pct = Math.round((count / denom) * 100);
                      return (
                        <div key={stage} className="space-y-1">
                          <div className="flex items-center justify-between text-base">
                            <span className="font-medium text-amber-950">{overviewParticipationLabel(stage)}</span>
                            <span className="text-amber-800/55">
                              {count} 人（佔全班 {pct}%）
                            </span>
                          </div>
                          <div className="h-3 overflow-hidden rounded-full bg-amber-100/80">
                            <div
                              className="h-full rounded-full transition-all duration-500"
                              style={{ width: `${pct}%`, backgroundColor: STAGE_COLORS[stage] }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <div className="mt-4 flex flex-wrap items-center justify-center gap-x-4 gap-y-2 text-sm text-amber-800/60">
                    <span className="font-medium text-amber-900">全班 {classTotal} 人</span>
                    {OVERVIEW_PARTICIPATION_ORDER.map((s) => (
                      <div key={s} className="flex items-center gap-1.5">
                        <span
                          className="inline-block h-2.5 w-2.5 rounded-full"
                          style={{ backgroundColor: STAGE_COLORS[s] }}
                        />
                        {overviewParticipationLabel(s)}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Student list */}
              <Card className={TEACHER_CARD}>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-base text-amber-950">
                    <FileText className="h-4 w-4 text-amber-700" />
                    學生清單
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  <div className="max-h-[360px] overflow-auto">
                    <table className="w-full text-base">
                      <thead className="sticky top-0 bg-amber-50/95">
                        <tr className="text-left text-amber-800/60">
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
                              className="cursor-pointer border-t border-amber-100 transition hover:bg-amber-50/70"
                              onClick={() => {
                                setSelectedStudentId(row.student_id);
                                setMainTab("tracking");
                              }}
                            >
                              <td className="px-4 py-2.5 font-medium text-amber-950">
                                {studentLabel(row)}
                                {needsAttention && (
                                  <span className="ml-1.5 text-base text-orange-600">需關注</span>
                                )}
                              </td>
                              <td className="px-4 py-2.5">
                                <span
                                  className="inline-block rounded-full px-2 py-0.5 text-base font-semibold text-white"
                                  style={{ backgroundColor: STAGE_COLORS[row.current_stage] ?? "#c4b5a0" }}
                                >
                                  {row.current_stage}
                                </span>
                              </td>
                              <td className="px-4 py-2.5">
                                <MiniBar pct={writePct} color="#6aaee0" />
                              </td>
                              <td className="px-4 py-2.5">
                                <MiniBar pct={okPct} color="#66b88f" />
                              </td>
                              <td className="pr-3">
                                <ChevronRight className="h-4 w-4 text-amber-800/40" />
                              </td>
                            </tr>
                          );
                        })}
                        {!(overview?.students?.length) && (
                          <tr>
                            <td colSpan={5} className="p-8 text-center text-amber-800/50">
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
          <TabsContent value="tracking" className="space-y-4">
            {!studentDetail ? trackingStudentSelect : null}
            {selectedStudentId && detailLoading ? (
              <div className="flex h-48 items-center justify-center text-amber-800/60">
                載入個人資料中…
              </div>
            ) : studentDetail ? (
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 lg:items-start">
                {/* Left: ORID completion + feedback analytics */}
                <div className="space-y-4">
                  {trackingStudentSelect}
                  <Card className={TEACHER_CARD}>
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base text-amber-950">ORID 完成狀態</CardTitle>
                      <p className="text-base text-amber-800/60">
                        {studentLabel(studentDetail)} — 第 {studentDetail.week} 週
                      </p>
                      <p className="text-xs text-amber-800/50">
                        各格「已完成」以本週寫入之草稿為準（與右欄「寫作完成」一致）；AI
                        教練若仍停留在較前面的階段，不影響已撰寫的格子。
                      </p>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      {ORID_STAGES.map((stage) => {
                        const hasDraft = (studentDetail.stages_with_draft ?? []).includes(stage);
                        const coachRaw = studentDetail.current_stage ?? "NOT_STARTED";
                        const coachIdx =
                          coachRaw === "NOT_STARTED"
                            ? -1
                            : ORID_STAGES.includes(coachRaw as (typeof ORID_STAGES)[number])
                              ? ORID_STAGES.indexOf(coachRaw as (typeof ORID_STAGES)[number])
                              : -1;
                        const stageIdx = ORID_STAGES.indexOf(stage);
                        const coachAtThis = coachIdx >= 0 && stageIdx === coachIdx;

                        let pct: number;
                        let label: string;
                        let emphasize: boolean;

                        if (hasDraft) {
                          label = "已完成";
                          pct = 100;
                          emphasize = false;
                        } else if (coachRaw === "NOT_STARTED") {
                          label = "未開始";
                          pct = 0;
                          emphasize = false;
                        } else if (coachAtThis) {
                          label = "輪到此格 · 尚未寫草稿";
                          pct = 33;
                          emphasize = true;
                        } else if (coachIdx >= 0 && stageIdx > coachIdx) {
                          label = "尚無草稿";
                          pct = 0;
                          emphasize = false;
                        } else {
                          label = "尚無草稿";
                          pct = 0;
                          emphasize = false;
                        }

                        return (
                          <div key={stage} className="space-y-1.5">
                            <div className="flex items-center justify-between text-base">
                              <span className="font-medium text-amber-950">{STAGE_LABELS[stage]}</span>
                              <span className={emphasize ? "font-medium text-amber-700" : "text-amber-800/55"}>
                                {label}
                              </span>
                            </div>
                            <div className="h-4 overflow-hidden rounded-full bg-amber-100/80">
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
                  <Card className={TEACHER_CARD}>
                    <CardHeader className="pb-2">
                      <CardTitle className="flex items-center gap-2 text-base text-amber-950">
                        <Activity className="h-4 w-4 text-[#6f58a8]" />
                        回饋分析
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-3 gap-3 text-center text-base">
                        <div className="rounded-xl border border-amber-100 bg-amber-50/70 p-3">
                          <p className="text-2xl font-bold text-amber-950">{studentDetail.feedback_click_count}</p>
                          <p className="mt-0.5 text-base text-amber-800/55">點擊次數</p>
                        </div>
                        <div className="rounded-xl border border-emerald-100 bg-[#edf7f1] p-3">
                          <p className="text-2xl font-bold text-[#3d8a63]">{studentDetail.feedback_ok_count}</p>
                          <p className="mt-0.5 text-base text-amber-800/55">通過次數</p>
                        </div>
                        <div className="rounded-xl border border-sky-100 bg-[#eef6fc] p-3">
                          <p className="text-2xl font-bold text-[#3d7eb0]">{studentDetail.feedback_ok_stages}/4</p>
                          <p className="mt-0.5 text-base text-amber-800/55">通過格數</p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>

                {/* Right: 數據／紀錄切換 + 統計或對話 thread */}
                <div className="flex flex-col gap-4">
                  <div className="flex shrink-0 rounded-xl border border-amber-200 bg-amber-100/60 p-0.5 text-sm font-medium text-amber-900/70 shadow-sm">
                    <button
                      type="button"
                      onClick={() => setTrackingRightTab("data")}
                      className={[
                        "flex-1 rounded-lg py-1.5 transition",
                        trackingRightTab === "data"
                          ? "bg-[#fffcf7] text-amber-950 shadow-sm"
                          : "hover:text-amber-950",
                      ].join(" ")}
                    >
                      數據
                    </button>
                    <button
                      type="button"
                      onClick={() => setTrackingRightTab("records")}
                      className={[
                        "flex-1 rounded-lg py-1.5 transition",
                        trackingRightTab === "records"
                          ? "bg-[#fffcf7] text-amber-950 shadow-sm"
                          : "hover:text-amber-950",
                      ].join(" ")}
                    >
                      紀錄
                    </button>
                  </div>

                  {trackingRightTab === "data" ? (
                    <>
                  <div className="grid grid-cols-2 gap-4">
                    <Card className={TEACHER_CARD}>
                      <CardContent className="flex items-center gap-3 p-4">
                        <div className="rounded-xl bg-[#eef6fc] p-2">
                          <MessageSquare className="h-5 w-5 text-[#3d7eb0]" />
                        </div>
                        <div>
                          <p className="text-2xl font-bold text-amber-950">{studentDetail.interaction_count}</p>
                          <p className="text-base text-amber-800/55">對話輪數</p>
                        </div>
                      </CardContent>
                    </Card>
                    <Card className={TEACHER_CARD}>
                      <CardContent className="flex items-center gap-3 p-4">
                        <div className="rounded-xl bg-[#edf7f1] p-2">
                          <FileText className="h-5 w-5 text-[#3d8a63]" />
                        </div>
                        <div>
                          <p className="text-2xl font-bold text-amber-950">{studentDetail.writing_completed_stages}/4</p>
                          <p className="text-base text-amber-800/55">寫作完成</p>
                        </div>
                      </CardContent>
                    </Card>
                  </div>

                  <Card className={TEACHER_CARD}>
                    <CardContent className="flex items-center gap-3 p-4">
                      <div className="rounded-xl bg-[#f3effa] p-2">
                        <Clock className="h-5 w-5 text-[#6f58a8]" />
                      </div>
                      <div>
                        <p className="text-base font-medium text-amber-950">最後活動</p>
                        <p className="text-base text-amber-800/55">
                          {formatLastActivityLocal(studentDetail.last_activity_at) ?? "尚無紀錄"}
                        </p>
                      </div>
                    </CardContent>
                  </Card>

                  {SHOW_TEACHER_POST_TEST_UI && (
                  <Card className={TEACHER_CARD}>
                    <CardHeader className="pb-2">
                      <CardTitle className="flex items-center justify-between gap-2 text-base text-amber-950">
                        <span className="flex items-center gap-2">
                          後測評分
                          <span className="text-base font-normal text-amber-800/55">（1–4 分）</span>
                        </span>
                        {writingRubric && (
                          <button
                            onClick={() => setRubricOpen((v) => !v)}
                            className="text-base font-normal text-amber-800 hover:underline"
                          >
                            {rubricOpen ? "收起評分標準" : "查看評分標準"}
                          </button>
                        )}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      {/* Rubric reference panel */}
                      {rubricOpen && writingRubric?.by_stage && (
                        <div className="mb-4 rounded-lg border border-amber-100 bg-amber-50 p-3 text-base">
                          {(["O", "R", "I", "D"] as const).map((s) => {
                            const items: RubricItem[] = writingRubric.by_stage[s] ?? [];
                            if (!items.length) return null;
                            const item = items[0];
                            return (
                              <div key={s} className="mb-2 last:mb-0">
                                <p className="mb-1 font-semibold text-amber-900">
                                  <span
                                    className="mr-1 inline-block rounded-full px-1.5 py-0.5 text-white"
                                    style={{ backgroundColor: STAGE_COLORS[s] ?? "#c4b5a0", fontSize: 12 }}
                                  >
                                    {s}
                                  </span>
                                  {item.name}
                                </p>
                                <div className="space-y-0.5 pl-5">
                                  {item.levels.map((lv) => (
                                    <p key={lv.label} className="leading-snug text-amber-900/70">
                                      <span className="font-medium text-amber-950">{lv.label}：</span>
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
                                style={{ backgroundColor: STAGE_COLORS[stage] ?? "#c4b5a0" }}
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
                                className="w-20 rounded-md border border-amber-200 px-2 py-1 text-center text-base focus:border-amber-400 focus:outline-none"
                              />
                              {saved && (
                                <span className="text-base text-amber-800/55">
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
                        className="kid-btn-primary mt-4 w-full"
                      >
                        {ptSaving ? "儲存中…" : "儲存評分"}
                      </button>
                    </CardContent>
                  </Card>
                  )}

                  <Card className={TEACHER_CARD}>
                    <CardHeader className="pb-2">
                      <CardTitle className="flex items-center gap-2 text-base text-amber-950">💡 教學回饋建議</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <TeachingTips student={studentDetail} selectedStudent={selectedStudent} />
                    </CardContent>
                  </Card>
                    </>
                  ) : (
                    <Card className={`${TEACHER_CARD} overflow-hidden`}>
                      <CardHeader className="pb-2 pt-4">
                        <CardTitle className="text-base text-amber-950">對話紀錄</CardTitle>
                        <p className="text-xs font-normal text-amber-800/55">
                          {studentLabel(studentDetail)} · 第 {studentDetail.week} 週寫作教練 · 僅顯示本週對話
                        </p>
                      </CardHeader>
                      <CardContent className="p-0">
                        {chatLoading ? (
                          <div
                            className={`flex items-center justify-center text-sm text-amber-800/55 ${recordsScrollClass}`}
                          >
                            載入對話中…
                          </div>
                        ) : chatError ? (
                          <div className={`bg-amber-50 p-4 text-sm text-amber-800 ${recordsScrollClass}`}>
                            {chatError}
                          </div>
                        ) : chatMessages.length === 0 ? (
                          <div
                            className={`flex items-center justify-center px-4 text-center text-sm text-amber-800/50 ${recordsScrollClass}`}
                          >
                            此週尚無對話紀錄，或學生尚未建立該週 session。
                          </div>
                        ) : (
                          <div
                            className={`space-y-3 border-t border-amber-100 bg-[#faf5eb]/80 px-3 py-3 ${recordsScrollClass}`}
                          >
                            {chatMessages.map((m) => {
                              const isStudent = m.sender === "student";
                              const stageTag = STAGE_LABELS[m.stage] ?? m.stage;
                              const who = isStudent ? "學生" : "AI 教練";
                              const timeStr = formatLastActivityLocal(m.created_at) ?? "";
                              return (
                                <div
                                  key={m.id}
                                  className={["flex w-full", isStudent ? "justify-end" : "justify-start"].join(" ")}
                                >
                                  <div
                                    className={[
                                      "max-w-[min(92%,28rem)] rounded-2xl px-3 py-2 text-sm shadow-sm",
                                      isStudent
                                        ? "bg-gradient-to-br from-amber-800 to-amber-900 text-amber-50"
                                        : "border border-amber-100 bg-white text-amber-950",
                                    ].join(" ")}
                                  >
                                    <div
                                      className={[
                                        "mb-1 flex flex-wrap items-center gap-2 text-[11px] font-medium",
                                        isStudent ? "text-amber-100/90" : "text-amber-800/55",
                                      ].join(" ")}
                                    >
                                      <span
                                        className="rounded-full px-1.5 py-0.5"
                                        style={{
                                          backgroundColor: isStudent ? "rgba(255,255,255,0.2)" : STAGE_COLORS[m.stage] ?? "#c4b5a0",
                                          color: "#fff",
                                        }}
                                      >
                                        {stageTag}
                                      </span>
                                      <span>{who}</span>
                                      {timeStr ? <span className="opacity-80">{timeStr}</span> : null}
                                    </div>
                                    <p className="whitespace-pre-wrap break-words leading-relaxed">{m.text}</p>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  )}
                </div>
              </div>
            ) : selectedStudentId ? (
              <div className="flex h-48 flex-col items-center justify-center gap-2 text-center text-amber-800/60">
                <p>無法載入此學生在第 {week} 週的摘要（請檢查網路或稍後再試）。</p>
                {detailError && (
                  <p className="max-w-lg rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-700">
                    伺服器說明：{detailError}
                  </p>
                )}
                <p className="text-xs">
                  若為 404／Student not in class：代表此學生不在目前選擇的班級名單中，請重選班級或於資料庫確認 StudentClassMembership。
                </p>
                <p className="text-xs">若剛切換週次／班級，請確認學生仍在名單中。</p>
              </div>
            ) : (
              <div className="flex h-48 items-center justify-center text-amber-800/60">
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
      <div className="h-2 w-20 overflow-hidden rounded-full bg-amber-100/80">
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <span className="w-8 text-right text-xs text-amber-800/55 sm:text-sm">{pct}%</span>
    </div>
  );
}

function StatCard({
  icon,
  iconBg = "bg-amber-50",
  label,
  value,
  sub,
}: {
  icon: React.ReactNode;
  iconBg?: string;
  label: string;
  value: string | number;
  sub: string;
}) {
  return (
    <Card className={TEACHER_CARD}>
      <CardContent className="flex items-center gap-4 p-4">
        <div className={`rounded-xl p-2 ${iconBg}`}>{icon}</div>
        <div>
          <p className="text-xs text-amber-800/55 sm:text-sm">{label}</p>
          <p className="text-2xl font-bold text-amber-950">{value}</p>
          <p className="text-xs text-amber-800/50 sm:text-sm">{sub}</p>
        </div>
      </CardContent>
    </Card>
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
    tips.push("此學生尚未開始對話，建議個別關心並引導進入系統。");
  } else if (student.interaction_count < 3) {
    tips.push("對話輪數偏低，可鼓勵學生多嘗試與 AI 來回討論以深化思考。");
  }

  const stageIdx = ORID_STAGES.indexOf(student.current_stage as typeof ORID_STAGES[number]);
  if (stageIdx <= 1 && student.interaction_count >= 5) {
    tips.push("對話輪數已不少但階段停留在前期，可能遇到瓶頸，建議引導。");
  }

  if (student.writing_completed_stages === 0 && student.interaction_count > 0) {
    tips.push("已有對話但尚未完成任何寫作，提醒學生完成反思寫作。");
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
    <ul className="space-y-2 text-base text-amber-950/85">
      {tips.map((t, i) => (
        <li key={i} className="flex items-start gap-2">
          <span className="mt-0.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-amber-600" />
          {t}
        </li>
      ))}
    </ul>
  );
}
