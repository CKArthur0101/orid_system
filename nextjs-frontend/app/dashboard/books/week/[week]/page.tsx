"use client";

import { useParams } from "next/navigation";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { BookHelperAvatar } from "@/components/orid/BookIllustration";
import { BadgeDisplay } from "@/components/orid/BadgeDisplay";
import { BadgeModal } from "@/components/orid/BadgeModal";
import { FeedbackGuideCard } from "@/components/orid/FeedbackGuideCard";
import { OridWeekHero } from "@/components/orid/OridWeekHero";
import { OridPartnerMascot } from "@/components/orid/OridMascotImage";
import { PersimmonBullet } from "@/components/orid/PersimmonBullet";
import { WritingPromptHelper } from "@/components/orid/WritingPromptHelper";
import { getBookWeekArt } from "@/lib/orid-book-art";
import { buildCoachOpeningMessage } from "@/lib/orid/coach-opening";
import { buildSynthesisOpeningMessage } from "@/lib/orid/synthesis-opening";
import { isEvenWeek, isOddWeek, priorOddWeek } from "@/lib/orid/week-flow";
import {
  ORID_BADGE_ORDER,
  SYNTHESIS_BADGE_ORDER,
  type BadgeId,
  calculateEarnedBadges,
  getNewlyEarnedBadges,
  stagesPassedFromWritingContent,
  stagesPassedFromWritingOk,
} from "@/lib/orid/badgeRules";
import { type ScoreResult } from "@/lib/orid/rubricScoring";
import {
  DRAFT_SAVE_ENCOURAGEMENT,
  STAGE_MISSION_META,
  SUBMIT_ALL_DONE_ENCOURAGEMENT,
  SUBMIT_PARTIAL_ENCOURAGEMENT,
} from "@/lib/orid-mission-copy";
import { ORID_UNLOCKED_WEEKS } from "@/lib/orid-week-access";
import { ORID_STAGE_THEME } from "@/lib/orid-stage-theme";
import { parseFeedbackNarration } from "@/lib/parse-feedback-narration";

type ChatMsg = { role: "student" | "ai"; text: string; stage?: string };

type StageKey = "O" | "R" | "I" | "D";
type DraftKey = "d1" | "d2";
type ConditionKey = "genai" | "template" | "control";

type WritingFeedback = {
  ok: boolean;
  praise?: string | null;
  missing: string[];
  suggestions: string[];
  example?: string | null;
  improved?: string | null;
  meta?: any;
};

type OridWritingStage = {
  d1: string;
  d2: string;
  feedback?: Partial<Record<DraftKey, WritingFeedback>>;
};

type Week2Flow = "orid_review" | "synthesis";

type OridWritingV1 = {
  schema: "orid_writing_v1";
  week: number;
  stages: Record<StageKey, OridWritingStage>;
  week2_flow?: Week2Flow;
  synthesis_draft?: string;
  synthesis_reading_reflection?: string;
  synthesis_round1_completed?: boolean;
  /** Snapshot of synthesis_draft after round-1 feedback; used to reset round when heavily rewritten. */
  synthesis_feedback_baseline_draft?: string;
  /** 舊版精靈資料；讀檔時保留，新 UI 不再寫入 */
  synthesis_evidence_notes?: string;
  synthesis_align_scaffold?: string;
  synthesis_short_draft?: string;
  synthesis_active_phase?: string;
  /** Persisted score snapshot for reload / research export */
  score?: Pick<ScoreResult, "totalScore" | "maxTotal">;
  earnedBadges?: BadgeId[];
};

type BookPackV1 = {
  schema: "book_pack_v1";
  book_title?: string;
  core_theme?: string[];
  key_events?: string[];
  writing_guide?: Partial<Record<StageKey, string>>;
};

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function isUuid(v?: string | null): v is string {
  return !!v && UUID_RE.test(v);
}

function formatApiError(status: number, body: string, fallback: string) {
  if (status === 401) return "登入狀態失效，請重新登入後再試一次。";
  if (status === 503) {
    const trimmed503 = (body || "").trim();
    if (trimmed503.startsWith("{")) {
      try {
        const parsed = JSON.parse(trimmed503) as { detail?: unknown };
        if (typeof parsed?.detail === "string" && parsed.detail.trim()) {
          return parsed.detail.trim();
        }
      } catch {
        /* fall through */
      }
    }
    return "連線暫時中斷，請再按一次「取得回饋」。";
  }
  const trimmed = (body || "").trim();
  if (trimmed.startsWith("{")) {
    try {
      const parsed = JSON.parse(trimmed) as { detail?: unknown };
      const detail = parsed?.detail;
      if (typeof detail === "string" && detail.trim()) return detail.trim();
      if (Array.isArray(detail) && detail.length > 0) {
        const first = detail[0] as { msg?: string };
        if (typeof first?.msg === "string" && first.msg.trim()) return first.msg.trim();
      }
    } catch {
      /* fall through */
    }
  }
  return trimmed || `${fallback}（${status}）`;
}

function localDraftStorageKey(sessionId: string, week: number) {
  return `orid-writing-draft:${sessionId}:${week}`;
}

function mergeProgressIntoWriting(
  writing: OridWritingV1,
  totalScore: number | null,
  badges: BadgeId[],
  options?: { includeScore?: boolean },
): OridWritingV1 {
  const next: OridWritingV1 = { ...writing };
  const includeScore = options?.includeScore !== false;
  if (includeScore && totalScore != null) {
    next.score = { totalScore, maxTotal: 90 };
  } else if (!includeScore) {
    delete next.score;
  }
  if (badges.length > 0) {
    next.earnedBadges = Array.from(new Set(badges)) as BadgeId[];
  }
  return next;
}

function extractProgressFromWriting(writing: OridWritingV1): {
  totalScore: number | null;
  earnedBadges: BadgeId[];
} {
  const totalScore =
    writing.score?.totalScore != null ? Number(writing.score.totalScore) : null;
  const earnedBadges = Array.isArray(writing.earnedBadges)
    ? (writing.earnedBadges.filter(Boolean) as BadgeId[])
    : [];
  return { totalScore, earnedBadges };
}

const STAGE_CARD_META: Record<StageKey, { title: string; question: string }> = {
  O: { title: "O 觀察 (Objective)", question: "我在故事中看到什麼？" },
  R: { title: "R 反思 (Reflective)", question: "這段故事讓我有什麼感覺？" },
  I: { title: "I 解釋 (Interpretive)", question: "這個故事想告訴我什麼？" },
  D: { title: "D 行動 (Decisional)", question: "我可以怎麼做得更好？" },
};

const STAGES: { key: StageKey; label: string }[] = [
  { key: "O", label: "O (Objective)" },
  { key: "R", label: "R (Reflective)" },
  { key: "I", label: "I (Interpretive)" },
  { key: "D", label: "D (Decisional)" },
];

const STAGE_TITLES: Record<StageKey, string> = {
  O: STAGE_MISSION_META.O.oridTitle,
  R: STAGE_MISSION_META.R.oridTitle,
  I: STAGE_MISSION_META.I.oridTitle,
  D: STAGE_MISSION_META.D.oridTitle,
};

const STAGE_WRITING_HINT: Record<StageKey, string> = {
  O: "寫故事裡誰做了什麼。",
  R: "寫你的感受和原因。",
  I: "寫你從故事學到什麼。",
  D: "寫以後可以怎麼做。",
};

type StageMissionStatus = "not_started" | "drafting" | "feedback" | "passed";

const STAGE_STATUS_TEXT: Record<StageMissionStatus, string> = {
  not_started: "尚未開始",
  drafting: "進行中",
  feedback: "已回饋",
  passed: "已通過",
};

/** 句型支架填空：用連續底線，避免全形＿在畫面上像 _ _ _ 斷開 */
const SCAFFOLD_BLANK = "______";

const STAGE_SCAFFOLD_LINES: Record<StageKey, string[]> = {
  O: [
    `故事中，${SCAFFOLD_BLANK}做了${SCAFFOLD_BLANK}。`,
    `一開始${SCAFFOLD_BLANK}，後來${SCAFFOLD_BLANK}。`,
    `我印象最深的是${SCAFFOLD_BLANK}。`,
  ],
  R: [
    `我覺得${SCAFFOLD_BLANK}，因為${SCAFFOLD_BLANK}。`,
    `看到${SCAFFOLD_BLANK}這一幕，我感到${SCAFFOLD_BLANK}。`,
    `如果我是${SCAFFOLD_BLANK}，我可能會覺得${SCAFFOLD_BLANK}。`,
  ],
  I: [
    `這個故事讓我學到${SCAFFOLD_BLANK}。`,
    `這件事提醒我要${SCAFFOLD_BLANK}，因為${SCAFFOLD_BLANK}。`,
    `我發現自己很在乎${SCAFFOLD_BLANK}。`,
  ],
  D: [
    `以後如果我遇到${SCAFFOLD_BLANK}，我會${SCAFFOLD_BLANK}。`,
    `下次當我想${SCAFFOLD_BLANK}的時候，我會先${SCAFFOLD_BLANK}。`,
    `我可以做的一件小事是：${SCAFFOLD_BLANK}。`,
  ],
};

function toChatMsg(m: any): ChatMsg | null {
  const text = String(m?.text ?? "").trim();
  if (!text) return null;
  const role: ChatMsg["role"] = m?.sender === "student" ? "student" : "ai";
  const stage = m?.stage ? String(m.stage) : undefined;
  return { role, text, stage };
}

function normalizeDraftKey(v: unknown, fallback: DraftKey): DraftKey {
  const s = String(v ?? "").toLowerCase();
  if (s === "d2") return "d2";
  if (s === "d1") return "d1";
  return fallback;
}

function coerceStageKey(v: unknown, fallback: StageKey = "O"): StageKey {
  const s = String(v ?? "").trim().toUpperCase();
  return s === "O" || s === "R" || s === "I" || s === "D" ? s : fallback;
}

function createEmptyWriting(week: number): OridWritingV1 {
  const stages: Record<StageKey, OridWritingStage> = {
    O: { d1: "", d2: "" },
    R: { d1: "", d2: "" },
    I: { d1: "", d2: "" },
    D: { d1: "", d2: "" },
  };
  const base: OridWritingV1 = {
    schema: "orid_writing_v1",
    week,
    stages,
  };
  if (week === 2) {
    return { ...base, week2_flow: "orid_review", synthesis_draft: "" };
  }
  return base;
}

function normalizeFeedbackObject(input: any): WritingFeedback | null {
  if (!input || typeof input !== "object") return null;
  const isComplete = input.ok === true && input.meta?.student_feedback_kind === "complete";
  return {
    ok: !!input.ok,
    praise: input.praise != null && input.praise !== "" ? String(input.praise) : null,
    // Keep at most 1 item; completion cards have empty arrays already from the backend,
    // but guard here for any legacy data.
    missing: Array.isArray(input.missing) ? input.missing.map(String).filter(Boolean).slice(0, 1) : [],
    suggestions: Array.isArray(input.suggestions)
      ? input.suggestions.map(String).filter(Boolean).slice(0, 1)
      : [],
    // Clear example on completion cards so the writing-hint panel doesn't show stale revision hints.
    example: isComplete ? null : (input.example ? String(input.example) : null),
    improved: input.improved ? String(input.improved) : null,
    meta: input.meta ?? null,
  };
}

function normalizeWritingContent(raw: unknown, week: number): OridWritingV1 {
  const empty = createEmptyWriting(week);
  if (!raw || typeof raw !== "object") return empty;

  const obj = raw as any;
  const stages: Record<StageKey, OridWritingStage> = {
    O: { d1: "", d2: "" },
    R: { d1: "", d2: "" },
    I: { d1: "", d2: "" },
    D: { d1: "", d2: "" },
  };

  for (const stage of STAGES.map((x) => x.key)) {
    const src = obj?.stages?.[stage] ?? {};
    const fbSrc = src?.feedback ?? {};
    const d1fb = normalizeFeedbackObject(fbSrc?.d1);
    const d2fb = normalizeFeedbackObject(fbSrc?.d2);

    stages[stage] = {
      d1: String(src?.d1 ?? ""),
      d2: String(src?.d2 ?? ""),
      feedback: {
        ...(d1fb ? { d1: d1fb } : {}),
        ...(d2fb ? { d2: d2fb } : {}),
      },
    };
  }

  const weekNum = Number(obj?.week ?? week) || week;
  const flow: Week2Flow | undefined =
    obj?.week2_flow === "synthesis" || obj?.week2_flow === "orid_review" ? obj.week2_flow : isEvenWeek(weekNum) ? "orid_review" : undefined;

  const o = obj as any;
  const base: OridWritingV1 = {
    schema: "orid_writing_v1",
    week: weekNum,
    stages,
    ...(flow ? { week2_flow: flow } : {}),
    ...(typeof o?.synthesis_draft === "string" ? { synthesis_draft: o.synthesis_draft } : {}),
    ...(typeof o?.score?.totalScore === "number"
      ? { score: { totalScore: o.score.totalScore, maxTotal: 90 } }
      : {}),
    ...(Array.isArray(o?.earnedBadges)
      ? { earnedBadges: o.earnedBadges.filter(Boolean) as BadgeId[] }
      : {}),
  };

  if (isEvenWeek(weekNum) && flow === "synthesis") {
    const out: OridWritingV1 = {
      ...base,
      synthesis_draft: typeof o.synthesis_draft === "string" ? o.synthesis_draft : "",
      synthesis_reading_reflection:
        typeof o.synthesis_reading_reflection === "string" ? o.synthesis_reading_reflection : "",
      synthesis_round1_completed: !!o.synthesis_round1_completed,
    };
    if (typeof o.synthesis_feedback_baseline_draft === "string") {
      out.synthesis_feedback_baseline_draft = o.synthesis_feedback_baseline_draft;
    }
    if (typeof o.synthesis_evidence_notes === "string") out.synthesis_evidence_notes = o.synthesis_evidence_notes;
    if (typeof o.synthesis_align_scaffold === "string") out.synthesis_align_scaffold = o.synthesis_align_scaffold;
    if (typeof o.synthesis_short_draft === "string") out.synthesis_short_draft = o.synthesis_short_draft;
    if (typeof o.synthesis_active_phase === "string") out.synthesis_active_phase = o.synthesis_active_phase;
    return out;
  }

  return base;
}

/** If the student rewrites the synthesis draft heavily, treat the next feedback as round 1 again. */
function synthesisDraftNeedsRound1Reset(baseline: string, current: string): boolean {
  const b = baseline.trim();
  const c = current.trim();
  if (!b) return false;
  if (c.length < b.length * 0.7) return true;
  if (Math.abs(c.length - b.length) > Math.max(80, b.length * 0.35)) return true;
  const probe = b.slice(0, Math.min(100, b.length));
  if (probe.length >= 30 && !c.includes(probe.slice(0, 30))) return true;
  return false;
}

function parseWritingRecordContent(content: unknown, week: number): OridWritingV1 {
  if (!content) return createEmptyWriting(week);

  if (typeof content === "object") {
    return normalizeWritingContent(content, week);
  }

  if (typeof content === "string") {
    try {
      return normalizeWritingContent(JSON.parse(content), week);
    } catch {
      return createEmptyWriting(week);
    }
  }

  return createEmptyWriting(week);
}

function deriveStageMissionStatus(stage: OridWritingStage): StageMissionStatus {
  const text = String(stage?.d1 ?? "").trim();
  const feedback = stage?.feedback?.d1;
  if (!text) return "not_started";
  if (!feedback) return "drafting";
  return feedback.ok ? "passed" : "feedback";
}

const LEGACY_COACH_WELCOME_SNIPPET = "先從左邊任一格";

function isLegacyCoachWelcome(text: string): boolean {
  return text.includes(LEGACY_COACH_WELCOME_SNIPPET);
}

function buildCoachWelcomeMsg(bookPack: BookPackV1 | null): ChatMsg {
  return {
    role: "ai",
    text: buildCoachOpeningMessage(bookPack),
  };
}

function refreshLegacyCoachWelcome(prev: ChatMsg[], bookPack: BookPackV1 | null): ChatMsg[] | null {
  if (prev.length === 1 && prev[0].role === "ai" && isLegacyCoachWelcome(prev[0].text)) {
    return [buildCoachWelcomeMsg(bookPack)];
  }
  return null;
}

const SYNTHESIS_OPENING_PREFIX = "歡迎來到第 ";

function getForceNewFromUrl(): boolean {
  if (typeof window === "undefined") return false;
  const sp = new URLSearchParams(window.location.search);
  const v = (sp.get("force_new") || "").trim().toLowerCase();
  return v === "1" || v === "true" || v === "yes";
}

function getConditionFromUrl(): ConditionKey | null {
  if (typeof window === "undefined") return null;
  const sp = new URLSearchParams(window.location.search);
  const v = (sp.get("condition") || "").trim().toLowerCase();
  if (v === "template" || v === "control") return "template";
  if (v === "genai") return "genai";
  return null;
}

function isControlConditionValue(v: unknown): boolean {
  const s = String(v ?? "").trim().toLowerCase();
  return s === "template" || s === "control";
}

export default function WeekBookPage() {
  const params = useParams();
  const raw = (params as any)?.week;
  const weekStr = Array.isArray(raw) ? raw[0] : raw;
  const weekNum = Number(weekStr);

  if (!weekStr || Number.isNaN(weekNum)) return <div className="p-6 text-lg">週次格式不正確</div>;
  if (weekNum < 1 || weekNum > ORID_UNLOCKED_WEEKS)
    return <div className="p-6 text-lg">此週次尚未開放</div>;

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [readingId, setReadingId] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [condition, setCondition] = useState<ConditionKey>("genai");

  const [readingReloadNonce, setReadingReloadNonce] = useState(0);
  const [bookPack, setBookPack] = useState<BookPackV1 | null>(null);

  const [historyLoaded, setHistoryLoaded] = useState(false);
  /** True after `/readings/:id` fetch finishes (bookPack may still be null). Used to avoid flashing the short placeholder opener. */
  const [readingContentReady, setReadingContentReady] = useState(false);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [seededInitial, setSeededInitial] = useState(false);
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  const emptyWriting = useMemo(() => createEmptyWriting(weekNum), [weekNum]);
  const [writingData, setWritingData] = useState<OridWritingV1>(emptyWriting);
  const [writingId, setWritingId] = useState<string | null>(null);
  const [writingHydratedSessionId, setWritingHydratedSessionId] = useState<string | null>(null);
  const [writingSubmitting, setWritingSubmitting] = useState(false);
  const [writingError, setWritingError] = useState<string | null>(null);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [encourageMsg, setEncourageMsg] = useState<string | null>(null);
  const encourageTimerRef = useRef<number | null>(null);
  const [oridCanForceNew, setOridCanForceNew] = useState(false);
  const [priorWeekData, setPriorWeekData] = useState<OridWritingV1 | null>(null);
  const [focusStage, setFocusStage] = useState<StageKey>("O");
  const [fbLoading, setFbLoading] = useState(false);
  const [fbError, setFbError] = useState<string | null>(null);
  /** Even-week synthesis: hide left ORID review panel to widen writing + partner. */
  const [oridPanelCollapsed, setOridPanelCollapsed] = useState(false);
  const [copyFlash, setCopyFlash] = useState<string | null>(null);

  // Synthesis chat tabs (week 2 synthesis phase only)
  type ChatTab = "synthesis" | "week1";
  const [chatTab, setChatTab] = useState<ChatTab>("synthesis");
  /** ORID feedback thread: student + O/R/I/D replies; excludes synthesis (ALL) and duplicate coach opener. */
  const ORID_STAGES = ["O", "R", "I", "D"] as const;
  const oridStageMessages = useMemo(
    () =>
      messages.filter(
        (m) =>
          m.stage !== "ALL" &&
          (m.role === "student" ||
            (ORID_STAGES as readonly string[]).includes(m.stage ?? "")),
      ),
    [messages],
  );
  /** Alias used by the synthesis tab's "上週回饋" panel. */
  const week1Messages = oridStageMessages;
  const synthMessages = useMemo(
    () => messages.filter((m) => m.stage === "ALL"),
    [messages],
  );
  const synthesisOpeningText = useMemo(
    () =>
      buildSynthesisOpeningMessage(priorWeekData, bookPack?.book_title, weekNum, {
        isControl: isControlConditionValue(condition),
      }),
    [priorWeekData, bookPack?.book_title, weekNum, condition],
  );
  /** 整合寫作 tab：開場引導（依上週內容）+ 本週 stage=ALL 的對話，不混入上週 ORID 回饋 */
  const synthesisTabMessages = useMemo((): ChatMsg[] => {
    const feedback = synthMessages;
    const opening: ChatMsg = {
      role: "ai",
      text: synthesisOpeningText,
      stage: "ALL",
    };
    const hasPersistedOpening = feedback.some(
      (m) => m.role === "ai" && m.text.startsWith(SYNTHESIS_OPENING_PREFIX),
    );
    if (hasPersistedOpening) return feedback;
    return [opening, ...feedback];
  }, [synthMessages, synthesisOpeningText]);

  // Score and badge state
  const [totalScore, setTotalScore] = useState<number | null>(null);
  const [earnedBadges, setEarnedBadges] = useState<BadgeId[]>([]);
  const [badgeModalQueue, setBadgeModalQueue] = useState<BadgeId[]>([]);
  const [promptViewCount, setPromptViewCount] = useState(0);
  const [progressHydratedSessionId, setProgressHydratedSessionId] = useState<string | null>(null);
  /** 避免連續按「取得回饋」時，先完成的請求在 finally 把 loading 清掉，導致後續請求沒有思考動畫 */
  const fbInflightRef = useRef(0);

  const awaitingFirstAiBubble =
    !!sessionId &&
    historyLoaded &&
    seededInitial &&
    readingContentReady &&
    messages.length === 0;

  const showAiTyping = !!sessionId && fbLoading;

  useLayoutEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, showAiTyping, chatTab, synthesisOpeningText]);

  useEffect(() => {
    return () => {
      if (encourageTimerRef.current !== null) {
        window.clearTimeout(encourageTimerRef.current);
        encourageTimerRef.current = null;
      }
    };
  }, []);

  function showEncourage(msg: string) {
    if (encourageTimerRef.current !== null) {
      window.clearTimeout(encourageTimerRef.current);
      encourageTimerRef.current = null;
    }
    setEncourageMsg(msg);
    encourageTimerRef.current = window.setTimeout(() => {
      setEncourageMsg(null);
      encourageTimerRef.current = null;
    }, 3500);
  }

  async function ensureNewOrLatestSession(forceNew: boolean, desiredCondition?: ConditionKey | null) {
    const qs = new URLSearchParams({
      week: String(weekNum),
      force_new: forceNew ? "true" : "false",
    });
    if (desiredCondition) qs.set("condition", desiredCondition);
    const res = await fetch(`/api/orid/sessions/ensure?${qs.toString()}`, {
      method: "POST",
      cache: "no-store",
    });
    const text = await res.text();
    if (!res.ok) {
      if (res.status === 401 && typeof window !== "undefined") {
        window.location.href = "/login";
      }
      if (res.status === 403) {
        throw new Error("目前無法重新開始（未授權）。");
      }
      throw new Error(formatApiError(res.status, text, "初始化失敗"));
    }
    return text ? JSON.parse(text) : null;
  }

  async function restartWeek() {
    try {
      setLoading(true);
      setError(null);

      if (typeof window !== "undefined" && sessionId) {
        try {
          localStorage.removeItem(localDraftStorageKey(sessionId, weekNum));
        } catch {
          /* ignore */
        }
      }

      const desiredCondition = getConditionFromUrl();
      const s = await ensureNewOrLatestSession(true, desiredCondition);
      const nextSessionId = isUuid(s?.id) ? String(s.id) : null;
      const rid = isUuid(s?.reading_id) ? String(s.reading_id) : null;

      setSessionId(nextSessionId);
      setReadingId(rid);
      const c = String(s?.condition ?? "genai").toLowerCase();
      setCondition((c === "control" ? "template" : c) as ConditionKey);
      setBookPack(null);
      setReadingContentReady(false);
      setReadingReloadNonce((n) => n + 1);

      // Re-run normal hydration flow for a brand-new session
      // (history -> reading -> first AI opener), instead of forcing ready flags.
      setHistoryLoaded(false);

      setWritingHydratedSessionId(null);
      setWritingId(null);
      setWritingData(emptyWriting);
      setPriorWeekData(null);
      setFbError(null);
      setSaveMsg(null);
      setEncourageMsg(null);
      setFocusStage("O");
      setMessages([]);
      setSeededInitial(false);
      setTotalScore(null);
      setEarnedBadges([]);
      setBadgeModalQueue([]);
      setProgressHydratedSessionId(null);
    } catch (e: any) {
      setError(e?.message ?? "重新開始失敗");
    } finally {
      setLoading(false);
    }
  }

  const [forceNewOnce] = useState<boolean>(() => getForceNewFromUrl());
  const [conditionFromUrl] = useState<ConditionKey | null>(() => getConditionFromUrl());

  useEffect(() => {
    const ac = new AbortController();
    (async () => {
      try {
        const r = await fetch("/api/orid/me/capabilities", {
          credentials: "include",
          signal: ac.signal,
          cache: "no-store",
        });
        if (!r.ok) return;
        const cap = await r.json();
        setOridCanForceNew(!!cap?.orid_can_force_new);
      } catch {
        // ignore
      }
    })();
    return () => ac.abort();
  }, []);

  useEffect(() => {
    if (!isEvenWeek(weekNum) || !sessionId) return;
    const priorWeek = priorOddWeek(weekNum);
    const ac = new AbortController();
    (async () => {
      try {
        const res = await fetch(`/api/orid/writings?session_id=${sessionId}&week=${priorWeek}&latest=true`, {
          credentials: "include",
          cache: "no-store",
          signal: ac.signal,
        });
        const text = await res.text();
        if (!res.ok) {
          setPriorWeekData(createEmptyWriting(priorWeek));
          return;
        }
        const list = text ? JSON.parse(text) : [];
        const latest = Array.isArray(list) ? list[0] : null;
        if (latest?.content) {
          setPriorWeekData(parseWritingRecordContent(latest.content, priorWeek));
        } else {
          setPriorWeekData(createEmptyWriting(priorWeek));
        }
      } catch {
        setPriorWeekData(createEmptyWriting(priorWeek));
      }
    })();
    return () => ac.abort();
  }, [weekNum, sessionId]);

  const w2Phase = isEvenWeek(weekNum) ? writingData.week2_flow ?? "orid_review" : null;
  const oridDisplay = isEvenWeek(weekNum) ? (priorWeekData ?? createEmptyWriting(priorOddWeek(weekNum))) : writingData;
  const showStageFeedbackButtons = isOddWeek(weekNum);
  const showSynthesisColumn = isEvenWeek(weekNum) && w2Phase === "synthesis";
  const oridReadOnly = isEvenWeek(weekNum);
  const showOridLeftPanel = !showSynthesisColumn || !oridPanelCollapsed;

  useEffect(() => {
    if (!showSynthesisColumn) {
      setOridPanelCollapsed(false);
      return;
    }
    try {
      const raw = window.localStorage.getItem(`orid-synth-orid-collapsed:w${weekNum}`);
      setOridPanelCollapsed(raw === "1");
    } catch {
      setOridPanelCollapsed(false);
    }
  }, [showSynthesisColumn, weekNum]);

  function setOridPanelCollapsedPersist(next: boolean) {
    setOridPanelCollapsed(next);
    if (!showSynthesisColumn) return;
    try {
      window.localStorage.setItem(`orid-synth-orid-collapsed:w${weekNum}`, next ? "1" : "0");
    } catch {
      /* ignore */
    }
  }

  const missionProgress = useMemo(() => {
    const data = isEvenWeek(weekNum) ? (priorWeekData ?? createEmptyWriting(priorOddWeek(weekNum))) : writingData;
    return STAGES.map(({ key }) => ({
      stage: key,
      status: deriveStageMissionStatus(data.stages[key]),
    }));
  }, [writingData, priorWeekData, weekNum]);
  const writtenCount = useMemo(
    () => missionProgress.filter((item) => item.status !== "not_started").length,
    [missionProgress],
  );
  const allStagesWritten = useMemo(
    () => STAGES.every(({ key }) => String(writingData.stages[key].d1 ?? "").trim().length > 0),
    [writingData],
  );

  const mainGridClass = showSynthesisColumn
    ? oridPanelCollapsed
      ? "orid-synthesis-grid grid min-h-0 w-full flex-1 grid-cols-1 gap-2 overflow-hidden max-md:gap-2.5 md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] md:gap-2 lg:gap-3"
      : "orid-synthesis-grid grid min-h-0 w-full flex-1 grid-cols-1 gap-2 overflow-hidden max-md:gap-2.5 md:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)_minmax(0,1fr)] md:gap-2 lg:gap-3"
    : "grid min-h-0 w-full flex-1 grid-cols-1 gap-2.5 overflow-hidden lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:gap-3";
  const visibleBadgeIds = isEvenWeek(weekNum) ? SYNTHESIS_BADGE_ORDER : ORID_BADGE_ORDER;

  const aiPartnerShellClass = showSynthesisColumn
    ? oridPanelCollapsed
      ? "kid-shell order-3 flex min-h-0 w-full min-w-0 flex-col overflow-hidden max-md:min-h-[50vh] md:order-2 md:col-start-2 md:row-start-1 md:h-full"
      : "kid-shell order-3 flex min-h-0 w-full min-w-0 flex-col overflow-hidden max-md:min-h-[50vh] md:order-3 md:col-start-3 md:row-start-1 md:h-full"
    : "kid-shell order-3 flex min-h-[32vh] w-full min-w-0 flex-col overflow-hidden lg:order-2 lg:col-start-2 lg:h-full lg:min-h-0 lg:row-start-1";

  const isControl = isControlConditionValue(condition);

  const activeStageDef = STAGES.find((s) => s.key === focusStage) ?? STAGES[0];
  const activeStage = activeStageDef.key;
  const activeTheme = ORID_STAGE_THEME[activeStage];
  const activeStageStatus = deriveStageMissionStatus(oridDisplay.stages[activeStage]);
  const activeMissionMeta = STAGE_MISSION_META[activeStage];
  const activeAiExample = oridDisplay.stages[activeStage].feedback?.d1?.example?.trim();
  const activeCardMeta = STAGE_CARD_META[activeStage];

  useEffect(() => {
    if (sessionId) return;
    let cancelled = false;

    (async () => {
      try {
        setLoading(true);
        setError(null);
        setHistoryLoaded(false);
        setReadingContentReady(false);
        setSeededInitial(false);
        setWritingHydratedSessionId(null);
        setProgressHydratedSessionId(null);

        let s: unknown = null;
        let lastErr: Error | null = null;
        for (let attempt = 0; attempt < 2; attempt++) {
          try {
            s = await ensureNewOrLatestSession(forceNewOnce, conditionFromUrl);
            lastErr = null;
            break;
          } catch (e: unknown) {
            lastErr = e instanceof Error ? e : new Error(String(e));
            if (attempt === 0) {
              await new Promise((r) => setTimeout(r, 400));
            }
          }
        }
        if (cancelled) return;
        if (lastErr) throw lastErr;

        if (isUuid((s as { id?: string })?.id)) {
          setSessionId(String((s as { id: string }).id));
          setHistoryLoaded(false);
        }
        if (isUuid((s as { reading_id?: string })?.reading_id)) {
          setReadingId(String((s as { reading_id: string }).reading_id));
          setReadingReloadNonce((n) => n + 1);
        }
        if ((s as { condition?: string })?.condition) {
          const c = String((s as { condition: string }).condition).toLowerCase();
          setCondition((c === "control" ? "template" : c) as ConditionKey);
        }
      } catch (e: unknown) {
        if (cancelled) return;
        const msg = e instanceof Error ? e.message : "初始化失敗";
        setError(msg);
        setHistoryLoaded(true);
        setReadingContentReady(true);
        setSeededInitial(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [weekNum, sessionId, forceNewOnce, conditionFromUrl]);

  useEffect(() => {
    if (!sessionId || historyLoaded) return;
    const ac = new AbortController();

    (async () => {
      try {
        const res = await fetch(`/api/orid/messages?session_id=${sessionId}&order=asc&limit=200`, {
          method: "GET",
          cache: "no-store",
          signal: ac.signal,
        });
        const text = await res.text();
        if (!res.ok) throw new Error(`載入聊天紀錄失敗：${res.status} ${text}`);

        const list = text ? JSON.parse(text) : [];
        const mapped: ChatMsg[] = Array.isArray(list)
          ? list.map(toChatMsg).filter((x): x is ChatMsg => x !== null)
          : [];

        if (mapped.length) {
          setMessages(mapped);
          setSeededInitial(false);
        } else {
          setMessages([]);
          setSeededInitial(true);
        }
      } catch (e: any) {
        if (e?.name === "AbortError") return;
        setError(e?.message ?? "載入聊天紀錄失敗");
        setMessages((prev) => (prev.length ? prev : []));
        setSeededInitial(true);
      } finally {
        if (!ac.signal.aborted) setHistoryLoaded(true);
      }
    })();

    return () => ac.abort();
  }, [sessionId, historyLoaded]);

  useEffect(() => {
    if (!readingId) {
      setReadingContentReady(true);
      return;
    }
    const ac = new AbortController();
    setReadingContentReady(false);

    (async () => {
      try {
        const res = await fetch(`/api/orid/readings/${readingId}`, {
          method: "GET",
          cache: "no-store",
          signal: ac.signal,
        });
        if (!res.ok) return;

        const data = await res.json();
        const c = data?.content;

        if (c && typeof c === "object" && c.schema === "book_pack_v1") {
          setBookPack(c as BookPackV1);
          return;
        }

        const raw = typeof c === "string" ? c : "";
        if (!raw) return;

        try {
          const parsed = JSON.parse(raw);
          if (parsed?.schema === "book_pack_v1") setBookPack(parsed as BookPackV1);
        } catch {
          // ignore
        }
      } catch {
        // ignore
      } finally {
        if (!ac.signal.aborted) setReadingContentReady(true);
      }
    })();

    return () => ac.abort();
  }, [readingId, readingReloadNonce]);

  useEffect(() => {
    if (!sessionId || writingHydratedSessionId === sessionId) return;
    const ac = new AbortController();

    (async () => {
      try {
        const res = await fetch(`/api/orid/writings?session_id=${sessionId}&week=${weekNum}&latest=true`, {
          method: "GET",
          credentials: "include",
          cache: "no-store",
          signal: ac.signal,
        });
        const text = await res.text();
        if (!res.ok) throw new Error(`載入寫作內容失敗：${res.status} ${text}`);

        const list = text ? JSON.parse(text) : [];
        const latest = Array.isArray(list) ? list[0] : null;
        if (latest?.id && isUuid(String(latest.id))) {
          setWritingId(String(latest.id));
        } else {
          setWritingId(null);
        }

        if (latest?.content) {
          const parsed = parseWritingRecordContent(latest.content, weekNum);
          setWritingData(parsed);
          const fromWriting = extractProgressFromWriting(parsed);
          if (!isControlConditionValue(condition) && fromWriting.totalScore != null) {
            setTotalScore(fromWriting.totalScore);
          }
          if (fromWriting.earnedBadges.length > 0) {
            setEarnedBadges((prev) =>
              Array.from(new Set([...prev, ...fromWriting.earnedBadges])) as BadgeId[],
            );
          }
        } else {
          let restored = false;
          if (typeof window !== "undefined") {
            try {
              const raw = localStorage.getItem(localDraftStorageKey(sessionId, weekNum));
              if (raw) {
                const parsed = JSON.parse(raw) as unknown;
                const normalized = normalizeWritingContent(parsed, weekNum);
                setWritingData(normalized);
                const fromWriting = extractProgressFromWriting(normalized);
                if (!isControlConditionValue(condition) && fromWriting.totalScore != null) {
                  setTotalScore(fromWriting.totalScore);
                }
                if (fromWriting.earnedBadges.length > 0) {
                  setEarnedBadges((prev) =>
                    Array.from(new Set([...prev, ...fromWriting.earnedBadges])) as BadgeId[],
                  );
                }
                restored = true;
              }
            } catch {
              /* ignore */
            }
          }
          if (!restored) setWritingData(createEmptyWriting(weekNum));
        }
      } catch {
        setWritingId(null);
        setWritingData(createEmptyWriting(weekNum));
      } finally {
        if (!ac.signal.aborted) setWritingHydratedSessionId(sessionId);
      }
    })();

    return () => ac.abort();
  }, [sessionId, weekNum, writingHydratedSessionId, condition]);

  useEffect(() => {
    if (!sessionId || progressHydratedSessionId === sessionId) return;
    const ac = new AbortController();

    (async () => {
      try {
        const qs = new URLSearchParams({
          session_id: sessionId,
          week: String(weekNum),
        });
        const res = await fetch(`/api/orid/progress?${qs.toString()}`, {
          credentials: "include",
          cache: "no-store",
          signal: ac.signal,
        });
        if (!res.ok) return;
        const data = await res.json();
        if (!isControlConditionValue(condition) && data?.totalScore != null) {
          setTotalScore(Number(data.totalScore));
        }
        if (Array.isArray(data?.earnedBadges) && data.earnedBadges.length > 0) {
          setEarnedBadges((prev) =>
            Array.from(new Set([...prev, ...(data.earnedBadges as BadgeId[])])) as BadgeId[],
          );
        }
      } catch {
        // ignore — progress restore is best-effort
      } finally {
        if (!ac.signal.aborted) setProgressHydratedSessionId(sessionId);
      }
    })();

    return () => ac.abort();
  }, [sessionId, weekNum, progressHydratedSessionId, condition]);

  /** 聊天載入後：奇數週空聊天才種 ORID 開場；整合寫作開場改由 synthesisTabMessages 顯示，不寫入全域 messages */
  useEffect(() => {
    if (!historyLoaded || !readingContentReady) return;
    if (isEvenWeek(weekNum) && writingData.week2_flow === "synthesis") return;

    setMessages((prev) => {
      const refreshed = refreshLegacyCoachWelcome(prev, bookPack);
      if (refreshed) return refreshed;

      if (!seededInitial) return prev;
      if (prev.length > 0) return prev;
      return [buildCoachWelcomeMsg(bookPack)];
    });
  }, [historyLoaded, readingContentReady, seededInitial, bookPack, weekNum, writingData.week2_flow]);

  function appendAiReply(text: unknown, stage?: string) {
    const reply = String(text ?? "").trim();
    if (!reply) return;
    setMessages((prev) => [...prev, { role: "ai", text: reply, stage }]);
  }

  async function persistWritingSnapshot(
    snapshot: OridWritingV1,
    totalScore: number | null,
    badges: BadgeId[],
  ) {
    if (!sessionId || !readingId) return;
    const payload = mergeProgressIntoWriting(snapshot, totalScore, badges, {
      includeScore: !isControl,
    });
    try {
      const r = await fetch(`/api/orid/writings`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reading_id: readingId,
          session_id: sessionId,
          week: weekNum,
          content: JSON.stringify(payload),
        }),
      });
      if (!r.ok) return;
      const data = await r.json();
      if (isUuid(data?.id)) setWritingId(String(data.id));
    } catch {
      // silent — progress restore still works from badge events
    }
  }

  async function runFeedback(stage: StageKey) {
    if (!sessionId || !showStageFeedbackButtons) return;

    const text = String(writingData.stages[stage]?.d1 ?? "").trim();
    if (!text) {
      setFbError("請先寫一些內容再取得回饋。");
      return;
    }

    fbInflightRef.current += 1;
    setFbLoading(true);
    setFbError(null);
    const draft: DraftKey = "d1";
    const optimisticStudent = `[${stage} 本段寫作]\n${text}`;
    setMessages((prev) => [...prev, { role: "student", text: optimisticStudent, stage }]);

    try {
      const r = await fetch("/api/orid/writing-coach/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: sessionId,
          student_text: text,
          stage,
          draft,
          source: "feedback_button",
          week: weekNum,
          save_feedback: true,
        }),
      });

      const raw = await r.text();
      if (!r.ok) throw new Error(formatApiError(r.status, raw, "回饋失敗"));

      const data = raw ? JSON.parse(raw) : {};
      appendAiReply(data?.ai_reply, stage);
      const outStage = coerceStageKey(data?.stage, stage);
      const outDraft: DraftKey = normalizeDraftKey(data?.meta?.draft ?? data?.draft, draft);

      const normalizedCondition = String(data?.meta?.condition ?? condition).toLowerCase();
      const isCompletionCard =
        !!data?.feedback_ok && data?.meta?.student_feedback_kind === "complete";
      const fb: WritingFeedback = {
        ok: !!data?.feedback_ok,
        praise: data?.feedback_praise ?? null,
        // Backend already trims to ≤1 for experimental group; keep slice(0,1) as safety net
        missing: Array.isArray(data?.feedback_missing)
          ? data.feedback_missing.map(String).slice(0, 1)
          : [],
        suggestions: Array.isArray(data?.feedback_suggestions)
          ? data.feedback_suggestions.map(String).slice(0, 1)
          : [],
        // Control group: never show AI example.
        // Experimental group completion card: clear example so the hint panel doesn't show revision hints.
        example:
          isControlConditionValue(normalizedCondition) || isCompletionCard
            ? null
            : (data?.feedback_example ?? null),
        improved: data?.feedback_improved ?? null,
        meta: data?.meta ?? null,
      };

      const nextWriting: OridWritingV1 = {
        ...writingData,
        stages: {
          ...writingData.stages,
          [outStage]: {
            ...writingData.stages[outStage],
            feedback: {
              ...(writingData.stages[outStage].feedback ?? {}),
              [outDraft]: fb,
            },
          },
        },
      };
      showEncourage(STAGE_MISSION_META[outStage].submitEncouragement);

      const savedId = String(data?.meta?.saved_to_writing_id ?? "");
      if (isUuid(savedId)) setWritingId(savedId);

      // Update score and badges from meta (with client-side fallback)
      const meta = data?.meta ?? {};
      const scoreFromMeta =
        meta.score?.totalScore != null ? Number(meta.score.totalScore) : null;
      let mergedBadges: BadgeId[] = Array.isArray(meta.earnedBadges)
        ? (meta.earnedBadges as BadgeId[])
        : [];
      if (mergedBadges.length === 0) {
        const stagesPassed = isControlConditionValue(normalizedCondition)
          ? stagesPassedFromWritingContent(nextWriting)
          : stagesPassedFromWritingOk(nextWriting);
        mergedBadges = calculateEarnedBadges({
          hasWritingContent: text.length > 0,
          hasUsedFeedbackOrPrompt: true,
          stagesPassed,
        });
      }
      const allBadges = Array.from(new Set([...earnedBadges, ...mergedBadges])) as BadgeId[];
      const newOnes: BadgeId[] = Array.isArray(meta.newlyEarnedBadges)
        ? (meta.newlyEarnedBadges as BadgeId[])
        : getNewlyEarnedBadges(earnedBadges, allBadges);

      const resolvedScore = scoreFromMeta ?? 0;
      setWritingData(
        mergeProgressIntoWriting(nextWriting, resolvedScore, allBadges, {
          includeScore: !isControl,
        }),
      );
      if (!isControl) setTotalScore(resolvedScore);
      setEarnedBadges(allBadges);
      if (newOnes.length > 0) {
        setBadgeModalQueue((prev) => [...prev, ...newOnes.filter((b) => !prev.includes(b))]);
      }
      await persistWritingSnapshot(nextWriting, resolvedScore, allBadges);
    } catch (e: any) {
      setFbError(e?.message ?? "回饋失敗");
    } finally {
      fbInflightRef.current -= 1;
      if (fbInflightRef.current <= 0) {
        fbInflightRef.current = 0;
        setFbLoading(false);
      }
    }
  }

  function appendStageToSynthesis(stage: StageKey) {
    const chunk = String(oridDisplay.stages[stage]?.d1 ?? "").trim();
    if (!chunk) {
      setFbError(`第 ${stage} 段還沒有內容可複製。`);
      setCopyFlash(null);
      return;
    }
    setFbError(null);
    setWritingData((prev) => {
      const cur = String(prev.synthesis_draft ?? "").trimEnd();
      const next = cur ? `${cur}\n${chunk}` : chunk;
      return { ...prev, synthesis_draft: next };
    });
    setCopyFlash(`已把 ${stage} 接到整合寫作後面`);
    window.setTimeout(() => setCopyFlash(null), 2200);
  }

  async function runSynthesisFeedback() {
    if (!sessionId || !isEvenWeek(weekNum) || isControl) return;

    const draft = String(writingData.synthesis_draft ?? "").trim();
    if (draft.length < 12) {
      setFbError("請先在整合稿區多寫一小段，再取得回饋。");
      return;
    }

    const feedbackRound = writingData.synthesis_round1_completed ? 2 : 1;

    fbInflightRef.current += 1;
    setFbLoading(true);
    setFbError(null);
    const optimisticStudent = `[整合寫作]\n${draft}`;
    setMessages((prev) => [...prev, { role: "student", text: optimisticStudent, stage: "ALL" }]);

    try {
      const r = await fetch("/api/orid/writing-coach/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: sessionId,
          student_text: draft,
          stage: "ALL",
          draft: "d1",
          source: "synthesis_feedback",
          week: weekNum,
          save_feedback: true,
          feedback_round: feedbackRound,
        }),
      });

      const raw = await r.text();
      if (!r.ok) throw new Error(formatApiError(r.status, raw, "整合回饋失敗"));

      const data = raw ? JSON.parse(raw) : {};
      appendAiReply(data?.ai_reply, "ALL");
      const savedId = String(data?.meta?.saved_to_writing_id ?? "");
      if (isUuid(savedId)) setWritingId(savedId);

      const meta = data?.meta ?? {};
      let nextWriting = writingData;
      if (feedbackRound === 1) {
        nextWriting = {
          ...writingData,
          synthesis_round1_completed: true,
          synthesis_feedback_baseline_draft: draft,
        };
        setWritingData(nextWriting);
      }
      if (Array.isArray(meta.earnedBadges)) {
        const merged = Array.from(
          new Set([...earnedBadges, ...(meta.earnedBadges as BadgeId[])]),
        ) as BadgeId[];
        const newOnes: BadgeId[] = Array.isArray(meta.newlyEarnedBadges)
          ? (meta.newlyEarnedBadges as BadgeId[])
          : getNewlyEarnedBadges(earnedBadges, merged);
        setEarnedBadges(merged);
        if (newOnes.length > 0) {
          setBadgeModalQueue((prev) => [...prev, ...newOnes.filter((b) => !prev.includes(b))]);
        }
        await persistWritingSnapshot(nextWriting, totalScore, merged);
      } else if (feedbackRound === 1) {
        await persistWritingSnapshot(nextWriting, totalScore, earnedBadges);
      }
    } catch (e: any) {
      setFbError(e?.message ?? "整合回饋失敗");
    } finally {
      fbInflightRef.current -= 1;
      if (fbInflightRef.current <= 0) {
        fbInflightRef.current = 0;
        setFbLoading(false);
      }
    }
  }

  async function runPromptUsage() {
    if (!sessionId) return;
    const wordCount = isEvenWeek(weekNum)
      ? String(writingData.synthesis_draft ?? "").trim().length
      : String(writingData.stages[focusStage]?.d1 ?? "").trim().length;
    try {
      const r = await fetch("/api/orid/prompt-usage", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: sessionId,
          week: weekNum,
          stage: focusStage,
          word_count: wordCount,
          prompt_view_count: 1,
        }),
      });
      if (!r.ok) return;
      const data = await r.json();
      setPromptViewCount(data.prompt_view_count ?? 0);
      if (Array.isArray(data.earnedBadges)) {
        const merged = data.earnedBadges as BadgeId[];
        const newOnes = Array.isArray(data.newlyEarnedBadges)
          ? (data.newlyEarnedBadges as BadgeId[])
          : [];
        setEarnedBadges(merged);
        if (newOnes.length > 0) {
          setBadgeModalQueue((prev) => [...prev, ...newOnes.filter((b) => !prev.includes(b))]);
        }
        await persistWritingSnapshot(writingData, totalScore, merged);
      }
    } catch {
      // silently ignore prompt usage logging errors
    }
  }

  async function saveWriting(label: "draft" | "submit") {
    if (!sessionId || !readingId) return;

    try {
      setWritingSubmitting(true);
      setWritingError(null);
      setSaveMsg(null);
      setEncourageMsg(null);

      if (label === "draft") {
        try {
          const payload = mergeProgressIntoWriting(writingData, totalScore, earnedBadges, {
            includeScore: !isControl,
          });
          if (typeof window !== "undefined") {
            localStorage.setItem(localDraftStorageKey(sessionId, weekNum), JSON.stringify(payload));
          }
          await persistWritingSnapshot(writingData, totalScore, earnedBadges);
          setWritingData(payload);
          setSaveMsg(DRAFT_SAVE_ENCOURAGEMENT);
        } catch {
          setWritingError("無法寫入本機儲存");
        }
        return;
      }

      const payload = mergeProgressIntoWriting(writingData, totalScore, earnedBadges, {
        includeScore: !isControl,
      });
      try {
        if (typeof window !== "undefined") {
          localStorage.setItem(localDraftStorageKey(sessionId, weekNum), JSON.stringify(payload));
        }
      } catch {
        /* ignore local backup failure; server submit may still succeed */
      }

      const content = JSON.stringify(payload);
      const r = await fetch(`/api/orid/writings`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reading_id: readingId,
          session_id: sessionId,
          week: weekNum,
          content,
          save_intent: "submit",
        }),
      });

      const text = await r.text();
      if (!r.ok) throw new Error(formatApiError(r.status, text, "寫作送出失敗"));

      const data = text ? JSON.parse(text) : null;
      if (isUuid(data?.id)) setWritingId(String(data.id));

      setWritingData(payload);
      try {
        if (typeof window !== "undefined") {
          localStorage.removeItem(localDraftStorageKey(sessionId, weekNum));
        }
      } catch {
        /* ignore */
      }

      setSaveMsg(allStagesWritten ? SUBMIT_ALL_DONE_ENCOURAGEMENT : SUBMIT_PARTIAL_ENCOURAGEMENT);
    } catch (e: any) {
      setWritingError(e?.message ?? "儲存失敗");
    } finally {
      setWritingSubmitting(false);
    }
  }

  async function submitWeek2PhaseToSynthesis() {
    if (!sessionId || !readingId || !isEvenWeek(weekNum)) return;
    try {
      setWritingSubmitting(true);
      setWritingError(null);
      setSaveMsg(null);
      setEncourageMsg(null);

      const next: OridWritingV1 = {
        ...writingData,
        week: weekNum,
        week2_flow: "synthesis",
        synthesis_draft: writingData.synthesis_draft ?? "",
      };
      const content = JSON.stringify(next);
      const r = await fetch(`/api/orid/writings`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reading_id: readingId,
          session_id: sessionId,
          week: weekNum,
          content,
        }),
      });

      const text = await r.text();
      if (!r.ok) throw new Error(formatApiError(r.status, text, "寫作送出失敗"));

      const data = text ? JSON.parse(text) : null;
      if (isUuid(data?.id)) setWritingId(String(data.id));

      try {
        if (typeof window !== "undefined") {
          localStorage.removeItem(localDraftStorageKey(sessionId, weekNum));
        }
      } catch {
        /* ignore */
      }

      setWritingData(next);
      setSaveMsg("已進入整合寫作階段 ✅");
      setChatTab("synthesis");
    } catch (e: any) {
      setWritingError(e?.message ?? "儲存失敗");
    } finally {
      setWritingSubmitting(false);
    }
  }

  return (
    <div className="flex h-full min-h-0 w-full flex-1 flex-col overflow-hidden">
      <div className={mainGridClass}>
        {showOridLeftPanel ? (
        <div className="order-1 flex min-h-0 w-full min-w-0 flex-col gap-2.5 overflow-hidden md:gap-1 lg:gap-2.5 md:h-full md:min-h-0">
          <OridWeekHero
            className="w-full"
            weekNum={weekNum}
            bookTitle={bookPack?.book_title}
            focusStage={focusStage}
            progress={missionProgress}
            writtenCount={writtenCount}
            onFocusStage={setFocusStage}
            loading={loading}
            error={error}
            showAdminControls={oridCanForceNew}
            onRestart={restartWeek}
            restartDisabled={loading}
            compact={showSynthesisColumn}
          />

          <div className="kid-shell flex min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden max-md:min-h-[40vh]">
            {isEvenWeek(weekNum) ? (
              <div className="flex shrink-0 items-center justify-between gap-2 border-b border-amber-100 px-3 py-1.5 text-[10px] text-amber-900/70 sm:text-xs">
                <span className="min-w-0 truncate text-left">
                  {w2Phase === "orid_review"
                    ? `顯示第 ${priorOddWeek(weekNum)} 週已儲存內容（唯讀）`
                    : `第 ${priorOddWeek(weekNum)} 週四段（唯讀）`}
                </span>
                {showSynthesisColumn ? (
                  <button
                    type="button"
                    className="inline-flex min-h-[30px] shrink-0 items-center gap-1 rounded-full border-2 border-amber-500 bg-amber-100 px-3 py-1 text-xs font-bold text-amber-950 shadow-sm transition hover:bg-amber-200"
                    onClick={() => setOridPanelCollapsedPersist(true)}
                  >
                    <span aria-hidden>←</span>
                    收起上週
                  </button>
                ) : null}
              </div>
            ) : null}

            <div className="flex min-h-0 w-full flex-1 flex-col p-2 md:p-1.5 lg:p-2">
              <div
                className={[
                  "relative flex min-h-0 w-full flex-1 flex-col rounded-2xl border-2 border-t-4 bg-white shadow-sm transition-all",
                  activeTheme.topBorder,
                  activeTheme.cardFocus,
                ].join(" ")}
              >
                <div className="relative z-20 flex shrink-0 items-start justify-between gap-2 overflow-visible px-2.5 pb-1 pt-2 sm:px-3 md:px-2 md:pb-0.5 md:pt-1.5 lg:px-3 lg:pb-1 lg:pt-2">
                  <div className="min-w-0 flex-1 pr-1 sm:pr-2">
                    <div className="flex min-w-0 flex-col gap-0.5">
                      <div className={`break-words text-sm font-bold leading-snug sm:text-sm ${activeTheme.titleColor}`}>
                        {weekNum === 1 ? activeCardMeta.title : STAGE_TITLES[activeStage]}
                      </div>
                    <div className="break-words text-[11px] leading-snug text-amber-900/65 sm:text-xs">
                      {weekNum === 1 ? activeCardMeta.question : STAGE_WRITING_HINT[activeStage]}
                    </div>
                    </div>
                    <span
                      className={[
                        "mt-1 inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium",
                        activeStageStatus === "passed"
                          ? "bg-emerald-50 text-emerald-800"
                          : "bg-amber-50 text-amber-900/60",
                      ].join(" ")}
                    >
                      {activeStageStatus === "passed" ? "✓ 已完成" : STAGE_STATUS_TEXT[activeStageStatus]}
                    </span>
                  </div>
                  {/* 徽章在左、按鈕在右，同一橫列 */}
                  <div className="flex max-w-[48%] shrink-0 flex-row items-center justify-end gap-1.5 overflow-visible sm:max-w-[46%] lg:max-w-[54%] lg:gap-2">
                    <BadgeDisplay
                      earnedBadges={earnedBadges}
                      badgeIds={visibleBadgeIds}
                      size={showSynthesisColumn ? 28 : 32}
                    />
                    {showSynthesisColumn ? (
                      <button
                        type="button"
                        className="inline-flex min-h-[34px] shrink-0 items-center justify-center rounded-full border-2 border-amber-500 bg-amber-50 px-3 py-1 text-xs font-bold text-amber-950 shadow-sm hover:bg-amber-100 sm:px-3.5"
                        title="接到整合寫作框後面"
                        onClick={() => appendStageToSynthesis(activeStage)}
                      >
                        複製
                      </button>
                    ) : null}
                    {showStageFeedbackButtons && !isControl ? (
                      <button
                        type="button"
                        className={[
                          "inline-flex shrink-0 items-center justify-center rounded-full border-2 px-3.5 py-1.5 text-xs font-bold shadow-sm transition-all sm:px-4 sm:py-2 sm:text-sm",
                          "disabled:cursor-not-allowed disabled:opacity-50",
                          activeStage === "O"
                            ? "border-sky-600 bg-sky-100 text-sky-950 hover:bg-sky-200"
                            : activeStage === "R"
                              ? "border-amber-600 bg-amber-100 text-amber-950 hover:bg-amber-200"
                              : activeStage === "I"
                                ? "border-emerald-600 bg-emerald-100 text-emerald-950 hover:bg-emerald-200"
                                : "border-violet-600 bg-violet-100 text-violet-950 hover:bg-violet-200",
                        ].join(" ")}
                        disabled={!sessionId || fbLoading}
                        onClick={() => runFeedback(activeStage)}
                      >
                        {fbLoading ? "回饋中…" : "取得回饋"}
                      </button>
                    ) : null}
                  </div>
                </div>

                <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden px-2 pt-0 sm:px-2.5 md:px-2 md:pt-0">
                  {weekNum === 1 ? (
                    <div className="mb-1 shrink-0 text-[10px] text-amber-900/60 sm:text-[11px] md:hidden lg:block lg:text-[11px]">
                      {activeMissionMeta.helperHint}
                    </div>
                  ) : null}

                  <div className={["flex min-h-0 flex-1", isControl ? "" : "gap-1.5"].join(" ")}>
                    <textarea
                      className={[
                        "min-h-[12rem] min-w-0 flex-1 resize-none overflow-y-auto rounded-xl border border-amber-100 bg-[#fffcf7] p-2.5 text-[15px] leading-relaxed outline-none placeholder:text-amber-900/35 focus:ring-2 read-only:bg-amber-50/40 md:min-h-0",
                        showSynthesisColumn ? "md:text-[13px] md:leading-snug lg:text-[15px] lg:leading-relaxed" : "",
                        activeTheme.inputFocus,
                      ].join(" ")}
                      placeholder={STAGE_WRITING_HINT[activeStage]}
                      value={oridDisplay.stages[activeStage].d1}
                      readOnly={oridReadOnly}
                      onFocus={() => setFocusStage(activeStage)}
                      onChange={
                        oridReadOnly
                          ? undefined
                          : (e) =>
                              setWritingData((prev) => ({
                                ...prev,
                                stages: {
                                  ...prev.stages,
                                  [activeStage]: { ...prev.stages[activeStage], d1: e.target.value },
                                },
                              }))
                      }
                    />
                    {!isControl ? (
                      <div
                        className={[
                          "orid-writing-hint-panel flex w-[34%] min-w-[6rem] shrink-0 flex-col overflow-y-auto rounded-xl border p-1.5 text-[11px] leading-snug sm:w-[32%] sm:min-w-[7rem] sm:p-2 sm:text-xs md:w-[30%] md:max-w-none lg:w-[28%]",
                          showSynthesisColumn ? "hidden min-[1100px]:flex" : "",
                          activeTheme.hintPanel,
                        ].join(" ")}
                      >
                        <div className={["mb-1 flex shrink-0 items-center gap-1 font-semibold", activeTheme.hintTitle].join(" ")}>
                          {weekNum === 1 ? <PersimmonBullet size={16} /> : null}
                          {activeAiExample ? "小幫手建議：" : "可以這樣開頭："}
                        </div>
                        <div className="flex flex-col gap-1">
                          {activeAiExample ? (
                            <div className="flex gap-1 break-words font-medium text-amber-950/85">
                              {weekNum === 1 ? <PersimmonBullet size={14} className="mt-0.5" /> : null}
                              <span>{activeAiExample}</span>
                            </div>
                          ) : (
                            STAGE_SCAFFOLD_LINES[activeStage].map((line) => (
                              <div key={line} className="flex gap-1 break-words">
                                <PersimmonBullet size={14} className="mt-0.5" />
                                <span>{line}</span>
                              </div>
                            ))
                          )}
                        </div>
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>
            </div>

            <div className="shrink-0 border-t border-amber-100 px-3 pb-2 pt-2 md:px-2 md:pb-1.5 md:pt-1.5 lg:px-3 lg:pb-2.5">
              <div className="flex flex-col gap-2">
                {isEvenWeek(weekNum) && w2Phase === "orid_review" ? (
                  <button
                    type="button"
                    className="kid-btn-primary w-full"
                    disabled={!sessionId || !readingId || writingSubmitting}
                    onClick={() => void submitWeek2PhaseToSynthesis()}
                  >
                    ⏭️ 進入整合寫作
                  </button>
                ) : (
                  <button
                    type="button"
                    className="kid-btn-primary w-full"
                    disabled={!sessionId || !readingId || writingSubmitting}
                    onClick={() => saveWriting("submit")}
                  >
                    {writingSubmitting ? "儲存中…" : "🌰 儲存我的寫作"}
                  </button>
                )}
              </div>
              {fbError && <div className="mt-1.5 whitespace-pre-wrap text-xs text-red-600 sm:text-sm">{fbError}</div>}
              {copyFlash && <div className="mt-1.5 text-xs font-medium text-emerald-700 sm:text-sm">{copyFlash}</div>}
              {encourageMsg && <div className="mt-1.5 text-xs font-medium text-amber-800 sm:text-sm">{encourageMsg}</div>}
              {saveMsg && <div className="mt-1.5 text-xs font-medium text-emerald-600 sm:text-sm">{saveMsg}</div>}
              {writingError && <div className="mt-1.5 whitespace-pre-wrap text-xs text-red-600 sm:text-sm">{writingError}</div>}
            </div>
          </div>
        </div>
        ) : null}

        {showSynthesisColumn ? (
          <div
            className={[
              "kid-shell order-2 flex min-h-0 w-full min-w-0 flex-col overflow-hidden max-md:min-h-[30vh] md:order-2 md:col-span-1 md:row-start-1 md:h-full",
              oridPanelCollapsed ? "md:col-start-1" : "md:col-start-2",
            ].join(" ")}
          >
            <div className="kid-section-header-partner flex items-center justify-between gap-2 px-2 py-2 md:px-2.5 md:py-2 lg:px-4 lg:py-3">
              <span className="text-xs font-bold text-amber-950 md:text-sm">整合寫作</span>
              <button
                type="button"
                className={[
                  "inline-flex min-h-[32px] shrink-0 items-center gap-1.5 rounded-full border-2 px-3 py-1 text-xs font-bold shadow-sm transition",
                  oridPanelCollapsed
                    ? "border-emerald-500 bg-emerald-50 text-emerald-900 hover:bg-emerald-100"
                    : "border-amber-500 bg-amber-100 text-amber-950 hover:bg-amber-200",
                ].join(" ")}
                onClick={() => setOridPanelCollapsedPersist(!oridPanelCollapsed)}
              >
                <span aria-hidden>{oridPanelCollapsed ? "→" : "←"}</span>
                {oridPanelCollapsed ? "展開上週" : "收起上週"}
              </button>
            </div>
            {oridPanelCollapsed ? (
              <div className="flex shrink-0 flex-wrap items-center gap-1.5 border-b border-amber-100 px-2 py-1.5">
                <span className="text-[10px] text-amber-900/65 sm:text-xs">接到後面：</span>
                {(["O", "R", "I", "D"] as StageKey[]).map((sk) => (
                  <button
                    key={sk}
                    type="button"
                    className="rounded-full border border-amber-300 bg-amber-50 px-2.5 py-0.5 text-[11px] font-bold text-amber-950 hover:bg-amber-100"
                    title={`把 ${sk} 接到整合寫作後面`}
                    onClick={() => appendStageToSynthesis(sk)}
                  >
                    複製 {sk}
                  </button>
                ))}
              </div>
            ) : null}
            <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-hidden p-2">
              <textarea
                className="min-h-0 w-full flex-1 resize-none rounded-xl border border-amber-100 bg-[#fffcf7] p-2.5 text-base leading-relaxed outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-300/30 md:p-3 md:text-sm lg:text-base"
                placeholder="依序寫：故事裡的事 → 感受與原因 → 學到什麼 → 以後會怎麼做……"
                value={writingData.synthesis_draft ?? ""}
                onChange={(e) => {
                  const nextDraft = e.target.value;
                  setWritingData((prev) => {
                    const baseline = String(prev.synthesis_feedback_baseline_draft ?? "").trim();
                    const needsReset =
                      prev.synthesis_round1_completed &&
                      synthesisDraftNeedsRound1Reset(baseline, nextDraft);
                    return {
                      ...prev,
                      synthesis_draft: nextDraft,
                      ...(needsReset
                        ? {
                            synthesis_round1_completed: false,
                            synthesis_feedback_baseline_draft: undefined,
                          }
                        : {}),
                    };
                  });
                }}
              />
              {copyFlash && oridPanelCollapsed ? (
                <div className="text-xs font-medium text-emerald-700">{copyFlash}</div>
              ) : null}
              {fbError && oridPanelCollapsed ? (
                <div className="whitespace-pre-wrap text-xs text-red-600">{fbError}</div>
              ) : null}
              {!isControl ? (
                <button
                  type="button"
                  className="kid-btn-primary shrink-0"
                  disabled={!sessionId || fbLoading}
                  onClick={() => void runSynthesisFeedback()}
                >
                  {fbLoading
                    ? "…"
                    : writingData.synthesis_round1_completed
                      ? "取得整合回饋（第二輪）"
                      : "取得整合回饋"}
                </button>
              ) : null}
            </div>
          </div>
        ) : null}

        <div className={aiPartnerShellClass}>
          {showSynthesisColumn ? (
            <>
              <div className="kid-section-header-partner shrink-0 px-2 py-2 md:px-2.5 md:py-2 lg:px-4 lg:py-3">
                <div className="text-xs font-bold text-amber-950 md:text-sm lg:text-base">
                  {isControl ? "寫作提示小幫手" : "AI 小幫手的回饋夥伴"}
                </div>
              </div>

              <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-[#fffcf7]">
                {/* Tab bar：控制組沒有對話，只保留整合寫作提示，不顯示分頁 */}
                {!isControl ? (
                  <div className="flex shrink-0 border-b border-amber-100 bg-amber-50/60">
                    {(["synthesis", "week1"] as const).map((tab) => (
                      <button
                        key={tab}
                        type="button"
                        onClick={() => setChatTab(tab)}
                        className={[
                          "min-h-[44px] flex-1 px-2 py-2.5 text-xs font-semibold transition-colors sm:text-sm",
                          chatTab === tab
                            ? "border-b-2 border-amber-500 text-amber-900"
                            : "text-amber-700/60 hover:text-amber-800",
                        ].join(" ")}
                      >
                        {tab === "synthesis" ? "整合寫作對話" : "上週對話"}
                      </button>
                    ))}
                  </div>
                ) : null}

                {isControl ? (
                  <WritingPromptHelper
                    focusStage={focusStage}
                    onPromptViewed={() => void runPromptUsage()}
                    synthesisMode
                    openingText={synthesisOpeningText}
                    week={weekNum}
                  />
                ) : (
                  <div className="min-h-0 flex-1 overflow-y-auto overscroll-y-contain p-2 sm:p-3">
                    {chatTab === "synthesis" ? (
                      <div className="flex flex-col gap-3">
                        {synthesisTabMessages.map((m, idx) => {
                          const isStudent = m.role === "student";
                          const parsedFeedback = !isStudent ? parseFeedbackNarration(m.text) : null;
                          const isOpening =
                            !isStudent && m.text.startsWith(SYNTHESIS_OPENING_PREFIX);
                          const helperAvatar = getBookWeekArt(weekNum) ? (
                            <BookHelperAvatar week={weekNum} size={44} />
                          ) : (
                            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white ring-2 ring-amber-100">
                              <OridPartnerMascot size={32} />
                            </div>
                          );
                          return (
                            <div
                              key={`syn-${idx}`}
                              className={[
                                "flex items-end gap-2",
                                isStudent ? "justify-end" : "justify-start",
                              ].join(" ")}
                            >
                              {!isStudent && <div className="shrink-0">{helperAvatar}</div>}
                              <div
                                className={
                                  isStudent
                                    ? "max-w-[min(88%,16rem)] shrink-0"
                                    : parsedFeedback
                                      ? "shrink min-w-0"
                                      : "max-w-[min(95%,22rem)] shrink min-w-0"
                                }
                              >
                                {parsedFeedback ? (
                                  <FeedbackGuideCard
                                    parsed={parsedFeedback}
                                    section3Label="③ 可以這樣修改"
                                  />
                                ) : (
                                  <div
                                    className={
                                      isStudent
                                        ? "kid-bubble-student"
                                        : isOpening
                                          ? "kid-bubble-ai border border-amber-100/80 bg-amber-50/40"
                                          : "kid-bubble-ai"
                                    }
                                  >
                                    <div className="whitespace-pre-wrap text-sm leading-relaxed">
                                      {m.text}
                                    </div>
                                  </div>
                                )}
                              </div>
                              {isStudent && (
                                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-100 text-lg ring-2 ring-amber-200/80">
                                  <span aria-hidden>🧒</span>
                                </div>
                              )}
                            </div>
                          );
                        })}
                        {synthesisTabMessages.length <= 1 &&
                          synthesisTabMessages.every((m) => m.role === "ai") && (
                            <p className="px-1 text-center text-xs text-amber-900/45">
                              寫完整合稿後，可以按下「取得整合回饋」。
                            </p>
                          )}
                      </div>
                    ) : week1Messages.length === 0 ? (
                      <div className="flex h-full min-h-[6rem] items-center justify-center px-2 text-center text-xs text-amber-900/50 sm:text-sm">
                        {!historyLoaded ? "載入中…" : "目前沒有上週對話紀錄。"}
                      </div>
                    ) : (
                      <div className="flex flex-col gap-3">
                        {week1Messages.map((m, idx) => {
                          const isStudent = m.role === "student";
                          const parsedFeedback = !isStudent ? parseFeedbackNarration(m.text) : null;
                          const helperAvatar = getBookWeekArt(weekNum) ? (
                            <BookHelperAvatar week={weekNum} size={44} />
                          ) : (
                            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white ring-2 ring-amber-100">
                              <OridPartnerMascot size={32} />
                            </div>
                          );
                          return (
                            <div
                              key={`w1-${idx}`}
                              className={[
                                "flex items-end gap-2",
                                isStudent ? "justify-end" : "justify-start",
                              ].join(" ")}
                            >
                              {!isStudent && <div className="shrink-0">{helperAvatar}</div>}
                              <div
                                className={
                                  isStudent
                                    ? "max-w-[min(88%,16rem)] shrink-0"
                                    : parsedFeedback
                                      ? "shrink min-w-0"
                                      : "max-w-[min(88%,18rem)] shrink-0"
                                }
                              >
                                {parsedFeedback ? (
                                  <FeedbackGuideCard parsed={parsedFeedback} />
                                ) : (
                                  <div className={isStudent ? "kid-bubble-student" : "kid-bubble-ai"}>
                                    <div className="whitespace-pre-wrap leading-relaxed">{m.text}</div>
                                  </div>
                                )}
                              </div>
                              {isStudent && (
                                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-100 text-lg ring-2 ring-amber-200/80">
                                  <span aria-hidden>🧒</span>
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                    <div ref={chatEndRef} className="h-0 shrink-0" aria-hidden />
                  </div>
                )}

                {showAiTyping && chatTab === "synthesis" && !isControl && (
                  <div className="shrink-0 border-t border-amber-100 bg-white/90 px-3 py-2" aria-live="polite">
                    <div className="flex items-end gap-2">
                      {getBookWeekArt(weekNum) ? (
                        <BookHelperAvatar week={weekNum} size={44} />
                      ) : (
                        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-white ring-2 ring-amber-100">
                          <OridPartnerMascot size={32} />
                        </div>
                      )}
                      <div className="kid-bubble-ai max-w-[16rem]">
                        <div className="flex items-center gap-1.5 py-0.5">
                          <span className="h-2 w-2 animate-bounce rounded-full bg-amber-500/80 [animation-delay:-0.24s]" />
                          <span className="h-2 w-2 animate-bounce rounded-full bg-amber-500/80 [animation-delay:-0.12s]" />
                          <span className="h-2 w-2 animate-bounce rounded-full bg-amber-500/80" />
                          <span className="ml-2 text-xs text-amber-900/70">松果小幫手正在思考…</span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </>
          ) : (
            /* ── Odd weeks (ORID) or orid_review phase: original chat ── */
            <>
              <div className="kid-section-header-partner">
                <div className="text-sm font-bold text-amber-950 sm:text-base">
                  {isControl ? "寫作提示小幫手" : "AI 小幫手的回饋夥伴"}
                </div>
              </div>

              {isControl ? (
                <WritingPromptHelper
                  focusStage={focusStage}
                  onPromptViewed={() => void runPromptUsage()}
                  week={weekNum}
                />
              ) : (
                <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-[#fffcf7]">
                  <div className="shrink-0 border-b border-amber-100 px-3 py-3 sm:px-4">
                    <div className="flex items-start gap-3">
                      {getBookWeekArt(weekNum) ? (
                        <BookHelperAvatar week={weekNum} size={68} />
                      ) : (
                        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-white ring-2 ring-amber-100">
                          <OridPartnerMascot size={40} />
                        </div>
                      )}
                      <div className="kid-bubble-ai max-w-[calc(100%-5rem)] text-xs leading-relaxed sm:max-w-[18rem] sm:text-sm">
                        你好！我是松果小夥伴 🌰
                        <br />
                        寫好後點「取得回饋」，我會用小小卡片回你，不會一次塞滿整頁喔。
                      </div>
                    </div>
                  </div>

                  <div className="min-h-0 flex-1 overflow-y-auto overscroll-y-contain p-2 sm:p-3">
                    {oridStageMessages.length === 0 ? (
                      <div className="flex h-full min-h-[6rem] items-center justify-center px-2 text-center text-xs text-amber-900/50 sm:text-sm">
                        {error && !sessionId
                          ? error
                          : !historyLoaded
                            ? "載入中…"
                            : seededInitial && !readingContentReady
                              ? "載入教材中…"
                              : awaitingFirstAiBubble
                                ? "小幫手正在準備開場…"
                                : "還沒有回饋訊息，先去寫作吧！"}
                      </div>
                    ) : (
                      <div className="flex flex-col gap-3">
                        {oridStageMessages.map((m, idx) => {
                          const isStudent = m.role === "student";
                          const parsedFeedback = !isStudent ? parseFeedbackNarration(m.text) : null;
                          const helperAvatar = getBookWeekArt(weekNum) ? (
                            <BookHelperAvatar week={weekNum} size={44} />
                          ) : (
                            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white ring-2 ring-amber-100">
                              <OridPartnerMascot size={32} />
                            </div>
                          );

                          return (
                            <div
                              key={idx}
                              className={["flex items-end gap-2", isStudent ? "justify-end" : "justify-start"].join(" ")}
                            >
                              {!isStudent && <div className="shrink-0">{helperAvatar}</div>}
                              <div
                                className={
                                  isStudent
                                    ? "max-w-[min(88%,16rem)] shrink-0"
                                    : parsedFeedback
                                      ? "shrink min-w-0"
                                      : "max-w-[min(88%,18rem)] shrink-0"
                                }
                              >
                                {parsedFeedback ? (
                                  <FeedbackGuideCard parsed={parsedFeedback} />
                                ) : (
                                  <div className={isStudent ? "kid-bubble-student" : "kid-bubble-ai"}>
                                    <div className="whitespace-pre-wrap leading-relaxed">{m.text}</div>
                                  </div>
                                )}
                              </div>
                              {isStudent && (
                                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-100 text-lg ring-2 ring-amber-200/80">
                                  <span aria-hidden>🧒</span>
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                    <div ref={chatEndRef} className="h-0 shrink-0" aria-hidden />
                  </div>

                  {showAiTyping && (
                    <div className="shrink-0 border-t border-amber-100 bg-white/90 px-3 py-2" aria-live="polite">
                      <div className="flex items-end gap-2">
                        {getBookWeekArt(weekNum) ? (
                          <BookHelperAvatar week={weekNum} size={44} />
                        ) : (
                          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-white ring-2 ring-amber-100">
                            <OridPartnerMascot size={32} />
                          </div>
                        )}
                        <div className="kid-bubble-ai max-w-[16rem]">
                          <div className="flex items-center gap-1.5 py-0.5">
                            <span className="h-2 w-2 rounded-full bg-amber-500/80 animate-bounce [animation-delay:-0.24s]" />
                            <span className="h-2 w-2 rounded-full bg-amber-500/80 animate-bounce [animation-delay:-0.12s]" />
                            <span className="h-2 w-2 rounded-full bg-amber-500/80 animate-bounce" />
                            <span className="ml-2 text-xs text-amber-900/70">松果小幫手正在思考…</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Badge congratulations modal */}
      {badgeModalQueue.length > 0 && (
        <BadgeModal
          badgeId={badgeModalQueue[0]}
          onClose={() => setBadgeModalQueue((prev) => prev.slice(1))}
        />
      )}
    </div>
  );
}
