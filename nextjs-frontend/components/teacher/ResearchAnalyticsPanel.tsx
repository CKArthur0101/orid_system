"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Download, FlaskConical, PieChart as PieIcon, TableProperties, TrendingUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

// ── Types (mirror TeacherResearchOverview schema) ───────────────────────────
type ResearchSummaryCards = {
  total_students: number;
  experimental_count: number;
  control_count: number;
  submitted_count: number;
  submission_rate: number;
  avg_guide_use_count: number;
  avg_total_score: number | null;
};

type ResearchGroupComparisonRow = {
  condition: string;
  student_count: number;
  avg_word_count: number;
  avg_revision_count: number;
  avg_guide_use_count: number;
  avg_badge_count: number;
  avg_orid_score: number | null;
  avg_sel_score: number | null;
  avg_total_score: number | null;
  submission_rate: number;
};

type ResearchWeeklyTrendPoint = {
  week: number;
  condition: string;
  avg_word_count: number;
  avg_revision_count: number;
  avg_guide_use_count: number;
  avg_badge_count: number;
  avg_orid_score: number | null;
  avg_sel_score: number | null;
  avg_total_score: number | null;
  student_count: number;
};

type ResearchCompletionDistribution = { submitted: number; not_submitted: number };

type ResearchStudentRow = {
  student_id: string;
  student_email: string;
  student_display_name: string;
  condition: string;
  week: number;
  task_type: string | null;
  word_count: number;
  save_count: number;
  revision_count: number;
  guide_use_count: number;
  badge_count: number;
  orid_score: number | null;
  sel_score: number | null;
  total_score: number | null;
  is_submitted: boolean;
};

type TeacherResearchOverview = {
  class_id: string;
  class_name: string;
  week: number | null;
  summary_cards: ResearchSummaryCards;
  group_comparison: ResearchGroupComparisonRow[];
  weekly_trends: ResearchWeeklyTrendPoint[];
  completion_distribution: ResearchCompletionDistribution;
  student_rows: ResearchStudentRow[];
};

// ── Constants ────────────────────────────────────────────────────────────────
const METRIC_OPTIONS = [
  { key: "avg_word_count", label: "字數" },
  { key: "avg_revision_count", label: "修改次數" },
  { key: "avg_guide_use_count", label: "引導使用次數" },
  { key: "avg_badge_count", label: "徽章數（參與）" },
  { key: "avg_orid_score", label: "AI 系統 ORID 分（探索）" },
  { key: "avg_sel_score", label: "AI 系統 SEL 分（探索）" },
  { key: "avg_total_score", label: "AI 系統總分（探索）" },
] as const;
type MetricKey = (typeof METRIC_OPTIONS)[number]["key"];

const CONDITION_LABEL: Record<string, string> = {
  experimental: "實驗組（AI 引導）",
  control: "控制組（固定提示）",
};
const CONDITION_SHORT_LABEL: Record<string, string> = {
  experimental: "實驗組",
  control: "控制組",
};
const CONDITION_COLOR: Record<string, string> = {
  experimental: "#c2691f",
  control: "#5f8f6e",
};
const DONUT_COLORS = ["#c2691f", "#e3d3ae"];

const TEACHER_CARD =
  "rounded-2xl border-2 border-amber-400/45 bg-[#fffcf7]/95 shadow-md shadow-amber-950/5";
const TEACHER_SELECT =
  "rounded-xl border-amber-200 bg-[#fffcf7] text-amber-950 focus:ring-amber-400/30";

const WEEK_OPTIONS = [1, 2, 3, 4, 5, 6];

function numOrZero(v: number | null | undefined): number {
  return typeof v === "number" ? v : 0;
}

// ── Main panel ───────────────────────────────────────────────────────────────
export function ResearchAnalyticsPanel({ classId }: { classId: string }) {
  const [week, setWeek] = useState<number | "all">("all");
  const [metric, setMetric] = useState<MetricKey>("avg_word_count");
  const [data, setData] = useState<TeacherResearchOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rowWeekFilter, setRowWeekFilter] = useState<number | "all">("all");
  const [rowConditionFilter, setRowConditionFilter] = useState<"all" | "experimental" | "control">("all");
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    if (!classId) return;
    let active = true;
    setLoading(true);
    setError(null);
    void (async () => {
      try {
        const qs = week === "all" ? "" : `?week=${week}`;
        const res = await fetch(`/api/teacher/classes/${classId}/research-overview${qs}`, {
          cache: "no-store",
        });
        if (!res.ok) {
          if (active) setError(`載入失敗（HTTP ${res.status}）`);
          return;
        }
        const json: TeacherResearchOverview = await res.json();
        if (active) setData(json);
      } catch {
        if (active) setError("載入失敗，請稍後再試");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [classId, week]);

  const cards = data?.summary_cards;
  const groupRows = data?.group_comparison ?? [];
  const trendRows = data?.weekly_trends ?? [];
  const completion = data?.completion_distribution ?? { submitted: 0, not_submitted: 0 };
  const studentRows = data?.student_rows ?? [];

  const filteredStudentRows = useMemo(() => {
    return studentRows.filter((r) => {
      if (rowWeekFilter !== "all" && r.week !== rowWeekFilter) return false;
      if (rowConditionFilter !== "all" && r.condition !== rowConditionFilter) return false;
      return true;
    });
  }, [studentRows, rowWeekFilter, rowConditionFilter]);

  const groupBarData = useMemo(
    () =>
      groupRows.map((r) => ({
        condition: CONDITION_SHORT_LABEL[r.condition] ?? r.condition,
        value: numOrZero((r as unknown as Record<string, number | null>)[metric]),
        fill: CONDITION_COLOR[r.condition] ?? "#a8845a",
      })),
    [groupRows, metric]
  );

  const trendLineData = useMemo(() => {
    const byWeek = new Map<number, Record<string, number>>();
    for (const t of trendRows) {
      const row = byWeek.get(t.week) ?? { week: t.week };
      row[t.condition] = numOrZero((t as unknown as Record<string, number | null>)[metric]);
      byWeek.set(t.week, row);
    }
    return Array.from(byWeek.values()).sort((a, b) => a.week - b.week);
  }, [trendRows, metric]);

  const donutData = [
    { name: "已提交", value: completion.submitted },
    { name: "未提交", value: completion.not_submitted },
  ];

  const metricLabel = METRIC_OPTIONS.find((m) => m.key === metric)?.label ?? metric;

  async function handleExport() {
    if (!classId) return;
    setExporting(true);
    try {
      const qs = week === "all" ? "" : `?week=${week}`;
      const res = await fetch(`/api/teacher/classes/${classId}/research-export${qs}`, {
        cache: "no-store",
      });
      if (!res.ok) return;
      const blob = await res.blob();
      const cd = res.headers.get("Content-Disposition") ?? "";
      const match = /filename="?([^"]+)"?/.exec(cd);
      const filename = match?.[1] ?? `research_week${week}.csv`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center text-amber-800/60">載入研究資料中…</div>
    );
  }
  if (error) {
    return <div className="flex h-64 items-center justify-center text-amber-800/60">{error}</div>;
  }

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-amber-200 bg-amber-50/70 px-4 py-3 text-sm leading-relaxed text-amber-950/85">
        <strong className="font-semibold">研究提醒：</strong>
        RQ1／RQ2 正式依變項為<strong>人工 rubric</strong>評分。下方 AI 系統分數僅供過程／探索參考；徽章為參與／階段完成指標，不是主要學習成效。RQ4（科技接受度）請用課堂 Google 表單或紙本，不在本系統內填寫。
      </div>
      {/* Controls row */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="text-base font-medium text-amber-900/75">週次：</span>
          <Select value={String(week)} onValueChange={(v) => setWeek(v === "all" ? "all" : Number(v))}>
            <SelectTrigger className={`w-[150px] ${TEACHER_SELECT}`}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部週次（1–6）</SelectItem>
              {WEEK_OPTIONS.map((w) => (
                <SelectItem key={w} value={String(w)}>
                  第 {w} 週
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <button
          type="button"
          onClick={() => void handleExport()}
          disabled={exporting}
          className="inline-flex items-center gap-2 rounded-xl border-2 border-amber-400/50 bg-[#fffcf7] px-4 py-2 text-sm font-semibold text-amber-900 shadow-sm transition hover:bg-amber-50 disabled:opacity-60"
        >
          <Download className="h-4 w-4" />
          {exporting ? "匯出中…" : "匯出研究 CSV"}
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={<FlaskConical className="h-5 w-5 text-[#3d7eb0]" />}
          iconBg="bg-[#eef6fc]"
          label="實驗組 / 控制組人數"
          value={`${cards?.experimental_count ?? 0} / ${cards?.control_count ?? 0}`}
          sub={`全班 ${cards?.total_students ?? 0} 人`}
        />
        <StatCard
          icon={<TableProperties className="h-5 w-5 text-[#3d8a63]" />}
          iconBg="bg-[#edf7f1]"
          label="提交率"
          value={`${Math.round((cards?.submission_rate ?? 0) * 100)}%`}
          sub={`${cards?.submitted_count ?? 0} 筆已提交`}
        />
        <StatCard
          icon={<TrendingUp className="h-5 w-5 text-[#b8741f]" />}
          iconBg="bg-[#fdf5e8]"
          label="平均引導使用次數"
          value={cards?.avg_guide_use_count ?? 0}
          sub="AI 回饋或提示小幫手"
        />
        <StatCard
          icon={<PieIcon className="h-5 w-5 text-[#6f58a8]" />}
          iconBg="bg-[#f3effa]"
          label="平均 AI 系統總分（探索）"
          value={cards?.avg_total_score != null ? cards.avg_total_score : "—"}
          sub="非正式依變項；滿分 90"
        />
      </div>

      {/* Metric switch */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-base font-medium text-amber-900/75">比較指標：</span>
        {METRIC_OPTIONS.map((m) => (
          <button
            key={m.key}
            type="button"
            onClick={() => setMetric(m.key)}
            className={[
              "rounded-full border px-3 py-1 text-sm font-medium transition",
              metric === m.key
                ? "border-amber-700 bg-amber-800 text-amber-50"
                : "border-amber-200 bg-[#fffcf7] text-amber-800/70 hover:bg-amber-50",
            ].join(" ")}
          >
            {m.label}
          </button>
        ))}
      </div>

      {/* Charts row 1: group bar + weekly trend */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card className={TEACHER_CARD}>
          <CardHeader className="pb-3">
            <CardTitle className="text-base text-amber-950">組別比較 — {metricLabel}</CardTitle>
            <p className="text-sm text-amber-800/60">實驗組（AI 引導）vs. 控制組（固定提示）</p>
          </CardHeader>
          <CardContent className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={groupBarData} margin={{ top: 8, right: 12, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0e4cc" />
                <XAxis dataKey="condition" tick={{ fontSize: 12, fill: "#7a5a2e" }} />
                <YAxis tick={{ fontSize: 12, fill: "#7a5a2e" }} />
                <Tooltip contentStyle={{ borderRadius: 12, borderColor: "#f0d9a8" }} />
                <Bar dataKey="value" radius={[8, 8, 0, 0]}>
                  {groupBarData.map((entry, idx) => (
                    <Cell key={idx} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className={TEACHER_CARD}>
          <CardHeader className="pb-3">
            <CardTitle className="text-base text-amber-950">六週趨勢 — {metricLabel}</CardTitle>
            <p className="text-sm text-amber-800/60">依週次比較兩組變化</p>
          </CardHeader>
          <CardContent className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendLineData} margin={{ top: 8, right: 12, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0e4cc" />
                <XAxis
                  dataKey="week"
                  tickFormatter={(w) => `第${w}週`}
                  tick={{ fontSize: 12, fill: "#7a5a2e" }}
                />
                <YAxis tick={{ fontSize: 12, fill: "#7a5a2e" }} />
                <Tooltip
                  contentStyle={{ borderRadius: 12, borderColor: "#f0d9a8" }}
                  labelFormatter={(w) => `第 ${w} 週`}
                  formatter={(value, name) => [value, CONDITION_LABEL[String(name)] ?? String(name)]}
                />
                <Legend formatter={(name) => CONDITION_LABEL[String(name)] ?? String(name)} />
                <Line
                  type="monotone"
                  dataKey="experimental"
                  stroke={CONDITION_COLOR.experimental}
                  strokeWidth={2.5}
                  dot={{ r: 3 }}
                  connectNulls
                />
                <Line
                  type="monotone"
                  dataKey="control"
                  stroke={CONDITION_COLOR.control}
                  strokeWidth={2.5}
                  dot={{ r: 3 }}
                  connectNulls
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Charts row 2: completion donut + student table */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,280px)_1fr]">
        <Card className={TEACHER_CARD}>
          <CardHeader className="pb-3">
            <CardTitle className="text-base text-amber-950">完成率</CardTitle>
            <p className="text-sm text-amber-800/60">
              {week === "all" ? "所有週次" : `第 ${week} 週`} 提交狀況
            </p>
          </CardHeader>
          <CardContent className="h-[220px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={donutData} dataKey="value" nameKey="name" innerRadius={50} outerRadius={80} paddingAngle={2}>
                  {donutData.map((_, idx) => (
                    <Cell key={idx} fill={DONUT_COLORS[idx % DONUT_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ borderRadius: 12, borderColor: "#f0d9a8" }} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className={TEACHER_CARD}>
          <CardHeader className="pb-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <CardTitle className="text-base text-amber-950">學生每週資料</CardTitle>
              <div className="flex items-center gap-2">
                <Select
                  value={String(rowWeekFilter)}
                  onValueChange={(v) => setRowWeekFilter(v === "all" ? "all" : Number(v))}
                >
                  <SelectTrigger className={`w-[110px] ${TEACHER_SELECT}`}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部週次</SelectItem>
                    {WEEK_OPTIONS.map((w) => (
                      <SelectItem key={w} value={String(w)}>
                        第 {w} 週
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select
                  value={rowConditionFilter}
                  onValueChange={(v) => setRowConditionFilter(v as "all" | "experimental" | "control")}
                >
                  <SelectTrigger className={`w-[140px] ${TEACHER_SELECT}`}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部組別</SelectItem>
                    <SelectItem value="experimental">實驗組</SelectItem>
                    <SelectItem value="control">控制組</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="max-h-[360px] overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-amber-50/95">
                  <tr className="text-left text-amber-800/60">
                    <th className="px-3 py-2">學生</th>
                    <th className="px-3 py-2">組別</th>
                    <th className="px-3 py-2 text-center">週</th>
                    <th className="px-3 py-2 text-center">字數</th>
                    <th className="px-3 py-2 text-center">修改</th>
                    <th className="px-3 py-2 text-center">引導</th>
                    <th className="px-3 py-2 text-center">徽章</th>
                    <th className="px-3 py-2 text-center">AI 總分（探索）</th>
                    <th className="px-3 py-2 text-center">已提交</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredStudentRows.map((r) => (
                    <tr key={`${r.student_id}-${r.week}`} className="border-t border-amber-100">
                      <td className="px-3 py-2 font-medium text-amber-950">
                        {r.student_display_name || r.student_email}
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className="rounded-full px-2 py-0.5 text-xs font-semibold text-white"
                          style={{ backgroundColor: CONDITION_COLOR[r.condition] ?? "#a8845a" }}
                        >
                          {CONDITION_SHORT_LABEL[r.condition] ?? r.condition}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-center">{r.week}</td>
                      <td className="px-3 py-2 text-center">{r.word_count}</td>
                      <td className="px-3 py-2 text-center">{r.revision_count}</td>
                      <td className="px-3 py-2 text-center">{r.guide_use_count}</td>
                      <td className="px-3 py-2 text-center">{r.badge_count}</td>
                      <td className="px-3 py-2 text-center">{r.total_score ?? "—"}</td>
                      <td className="px-3 py-2 text-center">{r.is_submitted ? "✓" : "—"}</td>
                    </tr>
                  ))}
                  {!filteredStudentRows.length && (
                    <tr>
                      <td colSpan={9} className="p-8 text-center text-amber-800/50">
                        尚無符合條件的資料
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// ── Sub-components ──────────────────────────────────────────────────────────
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
