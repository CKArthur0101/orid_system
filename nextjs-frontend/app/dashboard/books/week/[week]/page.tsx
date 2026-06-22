"use client";

import { useParams } from "next/navigation";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { FeedbackGuideCard } from "@/components/orid/FeedbackGuideCard";
import { OridMissionProgress } from "@/components/orid/OridMissionProgress";
import {
  DRAFT_SAVE_ENCOURAGEMENT,
  STAGE_MISSION_META,
  SUBMIT_ALL_DONE_ENCOURAGEMENT,
  SUBMIT_PARTIAL_ENCOURAGEMENT,
} from "@/lib/orid-mission-copy";
import { ORID_UNLOCKED_WEEKS } from "@/lib/orid-week-access";
import { parseFeedbackNarration } from "@/lib/parse-feedback-narration";

type ChatMsg = { role: "student" | "ai"; text: string };

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
  /** 舊版精靈資料；讀檔時保留，新 UI 不再寫入 */
  synthesis_evidence_notes?: string;
  synthesis_align_scaffold?: string;
  synthesis_short_draft?: string;
  synthesis_active_phase?: string;
};

type BookPackV1 = {
  schema: "book_pack_v1";
  book_title?: string;
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
  return { role, text };
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
  return {
    ok: !!input.ok,
    praise: input.praise != null && input.praise !== "" ? String(input.praise) : null,
    missing: Array.isArray(input.missing) ? input.missing.map(String).filter(Boolean).slice(0, 3) : [],
    suggestions: Array.isArray(input.suggestions)
      ? input.suggestions.map(String).filter(Boolean).slice(0, 3)
      : [],
    example: input.example ? String(input.example) : null,
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
    obj?.week2_flow === "synthesis" || obj?.week2_flow === "orid_review" ? obj.week2_flow : weekNum === 2 ? "orid_review" : undefined;

  const o = obj as any;
  const base: OridWritingV1 = {
    schema: "orid_writing_v1",
    week: weekNum,
    stages,
    ...(flow ? { week2_flow: flow } : {}),
    ...(typeof o?.synthesis_draft === "string" ? { synthesis_draft: o.synthesis_draft } : {}),
  };

  if (weekNum === 2 && flow === "synthesis") {
    const out: OridWritingV1 = {
      ...base,
      synthesis_draft: typeof o.synthesis_draft === "string" ? o.synthesis_draft : "",
      synthesis_reading_reflection:
        typeof o.synthesis_reading_reflection === "string" ? o.synthesis_reading_reflection : "",
      synthesis_round1_completed: !!o.synthesis_round1_completed,
    };
    if (typeof o.synthesis_evidence_notes === "string") out.synthesis_evidence_notes = o.synthesis_evidence_notes;
    if (typeof o.synthesis_align_scaffold === "string") out.synthesis_align_scaffold = o.synthesis_align_scaffold;
    if (typeof o.synthesis_short_draft === "string") out.synthesis_short_draft = o.synthesis_short_draft;
    if (typeof o.synthesis_active_phase === "string") out.synthesis_active_phase = o.synthesis_active_phase;
    return out;
  }

  return base;
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
  const title = String(bookPack?.book_title ?? "").trim();
  const book = title ? `《${title}》` : "這本書";
  return {
    role: "ai",
    text: [
      "哈囉！我是你的寫作小幫手 🤖",
      `左邊四格，你想先寫哪一格都可以喔！我們一起來想想讀${book}的心得。`,
      "寫不出來的時候，按那一格的「取得回饋」，我就會在這裡陪你喔！",
    ].join("\n"),
  };
}

function refreshLegacyCoachWelcome(prev: ChatMsg[], bookPack: BookPackV1 | null): ChatMsg[] | null {
  if (prev.length === 1 && prev[0].role === "ai" && isLegacyCoachWelcome(prev[0].text)) {
    return [buildCoachWelcomeMsg(bookPack)];
  }
  return null;
}

/** 第 2 週整合寫作：進聊天室時顯示，嵌入上週四格摘要與寫作架構（週一資料載入後會再刷新一次）。 */
function buildSynthesisWelcomeScaffold(week1: OridWritingV1 | null, bookPack: BookPackV1 | null): ChatMsg {
  const title = String(bookPack?.book_title ?? "").trim();
  const book = title ? `《${title}》` : "這本書";
  const w1 = week1 ?? createEmptyWriting(1);
  const blocks = STAGES.map(({ key }) => {
    const t = String(w1.stages[key].d1 ?? "").trim();
    return `${STAGE_TITLES[key]}\n${t || "（這一格還沒有內容）"}`;
  });
  const text = [
    `歡迎來到第 2 週「整合寫作」！`,
    `這週請把你在第 1 週寫的四段 ORID，收成一段讀起來順、又跟 ${book} 扣得住的心得。`,
    "",
    "── 你上週寫了什麼（也可對照左邊唯讀四格）──",
    "",
    ...blocks,
    "",
    "── 可以怎麼發揮（自由寫，不必照抄）──",
    "・開頭：一句話帶出「故事裡讓我印象最深的是…」",
    "・中間：把 O／R／I 用連接詞串起來，可以沿用你上週的句子做刪修、順一順。",
    "・收尾：呼應你上週 D，用一句寫「如果以後…我想先試試看…」。",
    "",
    "請在**中間大空白**寫整合稿；寫好後按下面的「取得整合回饋」。",
    "我會用三小段回覆你，標題跟第 1 週一樣好讀：「你已經做到：」「你可以再加強：」「試試看這樣寫：」。",
  ].join("\n");
  return { role: "ai", text };
}

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
  const [week1Data, setWeek1Data] = useState<OridWritingV1 | null>(null);
  const [focusStage, setFocusStage] = useState<StageKey>("O");
  const [fbLoading, setFbLoading] = useState(false);
  const [fbError, setFbError] = useState<string | null>(null);
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
  }, [messages, showAiTyping]);

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
      setWeek1Data(null);
      setFbError(null);
      setSaveMsg(null);
      setEncourageMsg(null);
      setFocusStage("O");
      setMessages([]);
      setSeededInitial(false);
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
    if (weekNum !== 2 || !sessionId) return;
    const ac = new AbortController();
    (async () => {
      try {
        const res = await fetch(`/api/orid/writings?session_id=${sessionId}&week=1&latest=true`, {
          credentials: "include",
          cache: "no-store",
          signal: ac.signal,
        });
        const text = await res.text();
        if (!res.ok) {
          setWeek1Data(createEmptyWriting(1));
          return;
        }
        const list = text ? JSON.parse(text) : [];
        const latest = Array.isArray(list) ? list[0] : null;
        if (latest?.content) {
          setWeek1Data(parseWritingRecordContent(latest.content, 1));
        } else {
          setWeek1Data(createEmptyWriting(1));
        }
      } catch {
        setWeek1Data(createEmptyWriting(1));
      }
    })();
    return () => ac.abort();
  }, [weekNum, sessionId]);

  const w2Phase = weekNum === 2 ? writingData.week2_flow ?? "orid_review" : null;
  const oridDisplay = weekNum === 2 ? (week1Data ?? createEmptyWriting(1)) : writingData;
  const showStageFeedbackButtons = weekNum === 1;
  const showSynthesisColumn = weekNum === 2 && w2Phase === "synthesis";
  const oridReadOnly = weekNum === 2;
  const missionProgress = useMemo(
    () =>
      STAGES.map(({ key }) => ({
        stage: key,
        status: deriveStageMissionStatus(writingData.stages[key]),
      })),
    [writingData],
  );
  const writtenCount = useMemo(
    () => missionProgress.filter((item) => item.status !== "not_started").length,
    [missionProgress],
  );
  const allStagesWritten = useMemo(
    () => STAGES.every(({ key }) => String(writingData.stages[key].d1 ?? "").trim().length > 0),
    [writingData],
  );

  const mainGridClass = showSynthesisColumn
    ? "grid min-h-0 flex-1 grid-cols-1 grid-rows-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1.2fr)] gap-3 overflow-hidden lg:grid-cols-3 lg:grid-rows-[minmax(0,1fr)] lg:gap-3"
    : "grid min-h-0 flex-1 grid-cols-1 grid-rows-[minmax(0,1fr)_minmax(0,1fr)] gap-3 overflow-hidden md:grid-cols-2 md:grid-rows-[minmax(0,1fr)] md:gap-3";

  useEffect(() => {
    if (sessionId) return;
    const ac = new AbortController();

    (async () => {
      try {
        setLoading(true);
        setError(null);

        const s = await ensureNewOrLatestSession(forceNewOnce, conditionFromUrl);
        if (ac.signal.aborted) return;

        if (isUuid(s?.id)) {
          setSessionId(String(s.id));
          setHistoryLoaded(false);
        }
        if (isUuid(s?.reading_id)) {
          setReadingId(String(s.reading_id));
          setReadingReloadNonce((n) => n + 1);
        }
        if (s?.condition) {
          const c = String(s.condition).toLowerCase();
          setCondition((c === "control" ? "template" : c) as ConditionKey);
        }
      } catch (e: any) {
        if (e?.name === "AbortError") return;
        setError(e?.message ?? "初始化失敗");
      } finally {
        if (!ac.signal.aborted) setLoading(false);
      }
    })();

    return () => ac.abort();
  }, [weekNum, sessionId, forceNewOnce]);

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
          setWritingData(parseWritingRecordContent(latest.content, weekNum));
        } else {
          let restored = false;
          if (typeof window !== "undefined") {
            try {
              const raw = localStorage.getItem(localDraftStorageKey(sessionId, weekNum));
              if (raw) {
                const parsed = JSON.parse(raw) as unknown;
                setWritingData(normalizeWritingContent(parsed, weekNum));
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
  }, [sessionId, weekNum, writingHydratedSessionId]);

  /** 聊天載入後：第 2 週整合寫作保證出現一次開場架構（不受 seededInitial 影響）；其餘週次維持原「空聊天才種 ORID 開場」。 */
  useEffect(() => {
    if (!historyLoaded || !readingContentReady) return;

    setMessages((prev) => {
      if (weekNum === 2 && writingData.week2_flow === "synthesis") {
        const hasScaffold = prev.some(
          (m) => m.role === "ai" && m.text.startsWith("歡迎來到第 2 週「整合寫作」"),
        );
        if (hasScaffold) return prev;
        const scaffold = buildSynthesisWelcomeScaffold(week1Data, bookPack);
        if (prev.length === 0) return [scaffold];
        if (prev.length === 1 && prev[0].role === "ai" && isLegacyCoachWelcome(prev[0].text)) {
          return [scaffold];
        }
        return [...prev, scaffold];
      }

      const refreshed = refreshLegacyCoachWelcome(prev, bookPack);
      if (refreshed) return refreshed;

      if (!seededInitial) return prev;
      if (prev.length > 0) return prev;
      return [buildCoachWelcomeMsg(bookPack)];
    });
  }, [historyLoaded, readingContentReady, seededInitial, bookPack, weekNum, writingData.week2_flow, week1Data]);

  /** 週一資料晚到時，更新已存在的整合寫作開場內容。 */
  useEffect(() => {
    if (weekNum !== 2 || writingData.week2_flow !== "synthesis" || !week1Data) return;
    setMessages((prev) => {
      const idx = prev.findIndex((m) => m.role === "ai" && m.text.startsWith("歡迎來到第 2 週「整合寫作」"));
      if (idx < 0) return prev;
      const next = [...prev];
      next[idx] = buildSynthesisWelcomeScaffold(week1Data, bookPack);
      return next;
    });
  }, [weekNum, writingData.week2_flow, week1Data, bookPack]);

  function appendAiReply(text: unknown) {
    const reply = String(text ?? "").trim();
    if (!reply) return;
    setMessages((prev) => [...prev, { role: "ai", text: reply }]);
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
    setMessages((prev) => [...prev, { role: "student", text: optimisticStudent }]);

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
      appendAiReply(data?.ai_reply);
      const outStage = coerceStageKey(data?.stage, stage);
      const outDraft: DraftKey = normalizeDraftKey(data?.meta?.draft ?? data?.draft, draft);

      const normalizedCondition = String(data?.meta?.condition ?? condition).toLowerCase();
      const fb: WritingFeedback = {
        ok: !!data?.feedback_ok,
        praise: data?.feedback_praise ?? null,
        missing: Array.isArray(data?.feedback_missing) ? data.feedback_missing.map(String) : [],
        suggestions: Array.isArray(data?.feedback_suggestions) ? data.feedback_suggestions.map(String) : [],
        example: isControlConditionValue(normalizedCondition) ? null : (data?.feedback_example ?? null),
        improved: data?.feedback_improved ?? null,
        meta: data?.meta ?? null,
      };

      setWritingData((prev) => {
        const next = {
          ...prev,
          stages: {
            ...prev.stages,
            [outStage]: {
              ...prev.stages[outStage],
              feedback: {
                ...(prev.stages[outStage].feedback ?? {}),
                [outDraft]: fb,
              },
            },
          },
        };
        return next;
      });
      showEncourage(STAGE_MISSION_META[outStage].submitEncouragement);

      const savedId = String(data?.meta?.saved_to_writing_id ?? "");
      if (isUuid(savedId)) setWritingId(savedId);
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

  async function runSynthesisFeedback() {
    if (!sessionId || weekNum !== 2) return;

    const draft = String(writingData.synthesis_draft ?? "").trim();
    if (draft.length < 12) {
      setFbError("請先在整合稿區多寫一小段，再取得回饋。");
      return;
    }

    fbInflightRef.current += 1;
    setFbLoading(true);
    setFbError(null);
    const optimisticStudent = `[整合寫作]\n${draft}`;
    setMessages((prev) => [...prev, { role: "student", text: optimisticStudent }]);

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
        }),
      });

      const raw = await r.text();
      if (!r.ok) throw new Error(formatApiError(r.status, raw, "整合回饋失敗"));

      const data = raw ? JSON.parse(raw) : {};
      appendAiReply(data?.ai_reply);
      const savedId = String(data?.meta?.saved_to_writing_id ?? "");
      if (isUuid(savedId)) setWritingId(savedId);
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

  async function saveWriting(label: "draft" | "submit") {
    if (!sessionId || !readingId) return;

    try {
      setWritingSubmitting(true);
      setWritingError(null);
      setSaveMsg(null);
      setEncourageMsg(null);

      if (label === "draft") {
        try {
          if (typeof window !== "undefined") {
            localStorage.setItem(localDraftStorageKey(sessionId, weekNum), JSON.stringify(writingData));
          }
          setSaveMsg(DRAFT_SAVE_ENCOURAGEMENT);
        } catch {
          setWritingError("無法寫入本機儲存");
        }
        return;
      }

      try {
        if (typeof window !== "undefined") {
          localStorage.setItem(localDraftStorageKey(sessionId, weekNum), JSON.stringify(writingData));
        }
      } catch {
        /* ignore local backup failure; server submit may still succeed */
      }

      const content = JSON.stringify(writingData);
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

      setSaveMsg(allStagesWritten ? SUBMIT_ALL_DONE_ENCOURAGEMENT : SUBMIT_PARTIAL_ENCOURAGEMENT);
    } catch (e: any) {
      setWritingError(e?.message ?? "儲存失敗");
    } finally {
      setWritingSubmitting(false);
    }
  }

  async function submitWeek2PhaseToSynthesis() {
    if (!sessionId || !readingId || weekNum !== 2) return;
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
      setMessages((prev) => {
        const scaffold = buildSynthesisWelcomeScaffold(week1Data, bookPack);
        if (prev.length === 1 && prev[0].role === "ai" && isLegacyCoachWelcome(prev[0].text)) {
          return [scaffold];
        }
        return [...prev, scaffold];
      });
    } catch (e: any) {
      setWritingError(e?.message ?? "儲存失敗");
    } finally {
      setWritingSubmitting(false);
    }
  }

  const STAGE_COLORS: Record<StageKey, string> = {
    O: "from-sky-400 to-sky-500",
    R: "from-amber-400 to-orange-500",
    I: "from-emerald-400 to-teal-500",
    D: "from-violet-400 to-purple-500",
  };

  const STAGE_EMOJI: Record<StageKey, string> = { O: "👀", R: "💭", I: "💡", D: "🎯" };

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col gap-2 overflow-hidden sm:gap-2.5">
      {/* Hero banner — compact for tablet viewport */}
      <div className="shrink-0 rounded-xl bg-gradient-to-r from-sky-500 to-blue-600 px-3 py-1.5 text-white shadow-md sm:px-4 sm:py-2">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <div className="min-w-0 flex-1">
            <h1 className="text-base font-bold leading-tight sm:text-lg">📖 AI–ORID 反思寫作</h1>
            <p className="truncate text-[11px] leading-tight text-sky-100 sm:text-xs">
              {weekNum === 1 ? "第 1 週｜完成四個反思小任務" : `第 ${weekNum} 週｜先寫作（左）→ 回饋夥伴（右）`}
              {bookPack?.book_title ? `｜${bookPack.book_title}` : ""}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
            {loading ? (
              <span className="text-[10px] text-sky-200 sm:text-xs">初始化中…</span>
            ) : error ? (
              <span className="rounded-md bg-red-500/20 px-1.5 py-0.5 text-[10px] text-white sm:text-xs">{error}</span>
            ) : (
              <span className="rounded-full bg-white/20 px-1.5 py-0.5 text-[10px] backdrop-blur-sm sm:text-xs">{condition}</span>
            )}
            {oridCanForceNew ? (
              <button
                type="button"
                onClick={restartWeek}
                disabled={loading}
                className="rounded-md bg-white/20 px-2 py-0.5 text-[10px] font-medium backdrop-blur-sm transition hover:bg-white/30 disabled:opacity-50 sm:px-2.5 sm:py-1 sm:text-xs"
                title="開新 session、清空聊天與寫作（僅實驗管理員）"
              >
                重新開始本週
              </button>
            ) : null}
          </div>
        </div>

        {/* 四格皆可寫；高亮目前關注的寫作區（點格子或輸入時可切換） */}
        <div className="mt-1 flex flex-wrap gap-1">
          {STAGES.map((s) => {
            const active = focusStage === s.key;
            return (
              <button
                key={s.key}
                type="button"
                onClick={() => setFocusStage(s.key)}
                className={[
                  "inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-[10px] font-medium transition-all sm:px-2.5 sm:text-xs",
                  active ? "bg-white text-sky-700 shadow-sm" : "bg-white/15 text-sky-100 hover:bg-white/25",
                ].join(" ")}
              >
                <span className="text-[11px] sm:text-xs">{STAGE_EMOJI[s.key]}</span>
                {s.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* 單屏：左 2×2 四格、右聊天；不超過視窗高度，過長只在各欄內捲動 */}
      <div className={mainGridClass}>
        <div className="kid-shell order-1 flex h-full min-h-0 flex-col overflow-hidden md:h-full">
          <div className="kid-section-header shrink-0 justify-between !py-1.5">
            <div className="flex items-center gap-1.5">
              <span className="text-base">✍️</span>
              <span className="text-xs font-bold sm:text-sm">反思寫作</span>
            </div>
            {weekNum === 2 ? (
              <span className="max-w-[14rem] text-right text-[10px] leading-snug text-sky-100 sm:max-w-none sm:text-xs">
                {w2Phase === "orid_review" ? "顯示第 1 週已儲存內容（唯讀）" : "第 1 週四段（唯讀）"}
              </span>
            ) : null}
          </div>
          {weekNum === 1 ? (
            <div className="shrink-0 px-2 pb-1 sm:px-3">
              <OridMissionProgress progress={missionProgress} writtenCount={writtenCount} onFocusStage={setFocusStage} />
            </div>
          ) : null}

          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
              <div className="grid min-h-0 flex-1 grid-cols-1 gap-2 p-2 max-sm:[grid-template-rows:repeat(4,minmax(0,1fr))] sm:grid-cols-2 sm:grid-rows-2 sm:[grid-template-rows:repeat(2,minmax(0,1fr))] sm:[grid-template-columns:repeat(2,minmax(0,1fr))]">
                {STAGES.map((s) => {
                  const stage = s.key;
                  const isFocused = focusStage === stage;
                  const stageStatus = deriveStageMissionStatus(writingData.stages[stage]);
                  const missionMeta = STAGE_MISSION_META[stage];

                  return (
                    <div
                      key={stage}
                      className={[
                        "flex min-h-0 flex-col rounded-xl border p-1.5 sm:p-1.5 md:h-full md:min-h-0",
                        isFocused
                          ? "border-sky-300 bg-sky-50/40 shadow-sm ring-1 ring-sky-200"
                          : "border-slate-200 bg-white hover:border-sky-200",
                      ].join(" ")}
                    >
                      <div className="flex shrink-0 flex-wrap items-start justify-between gap-1.5">
                        <div className="relative min-w-0 flex-1">
                          <div className="flex min-w-0 items-center gap-1.5">
                            <button
                              type="button"
                              className={`peer inline-flex h-6 w-6 shrink-0 cursor-help items-center justify-center rounded-md bg-gradient-to-br ${STAGE_COLORS[stage]} text-xs text-white shadow-sm outline-none ring-offset-2 transition hover:brightness-105 focus-visible:ring-2 focus-visible:ring-sky-400 sm:h-7 sm:w-7 sm:text-sm`}
                              aria-label={`${STAGE_TITLES[stage]}：查看寫作小提示`}
                            >
                              {STAGE_EMOJI[stage]}
                            </button>
                            <div className="min-w-0">
                              <div className="truncate text-xs font-bold leading-tight text-slate-700 sm:text-[13px]">
                                {weekNum === 1 ? missionMeta.missionTitle : STAGE_TITLES[stage]}
                              </div>
                              {weekNum === 1 ? (
                                <div className="text-[10px] text-slate-500 sm:text-[11px]">{missionMeta.oridTitle}</div>
                              ) : null}
                            </div>
                          </div>
                          {weekNum === 1 ? (
                            <div className="mt-1 text-[10px] leading-snug text-slate-600 sm:text-[11px]">💡 {missionMeta.helperHint}</div>
                          ) : null}
                          <div
                            role="tooltip"
                            className="pointer-events-none invisible absolute left-0 top-[calc(100%+0.35rem)] z-30 w-[min(18rem,calc(100vw-4rem))] rounded-xl border border-sky-100 bg-white p-3 text-left text-[11px] leading-relaxed text-slate-600 opacity-0 shadow-lg ring-1 ring-slate-200/80 transition-opacity duration-150 peer-hover:visible peer-hover:opacity-100 peer-focus:visible peer-focus:opacity-100 peer-focus-visible:visible peer-focus-visible:opacity-100 sm:text-xs"
                          >
                            {STAGE_WRITING_HINT[stage]}
                          </div>
                        </div>
                        {showStageFeedbackButtons ? (
                          <div className="flex shrink-0 items-center gap-1">
                            <span className="rounded-full border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[10px] text-slate-600 sm:text-[11px]">
                              {STAGE_STATUS_TEXT[stageStatus]}
                            </span>
                            <button
                              type="button"
                              className="kid-btn-primary shrink-0 !px-2 !py-0.5 !text-[10px] sm:!text-[11px]"
                              disabled={!sessionId || fbLoading}
                              onClick={() => runFeedback(stage)}
                            >
                              {fbLoading ? "…" : "取得回饋"}
                            </button>
                          </div>
                        ) : (
                          <span className="text-[10px] text-slate-400 sm:text-xs"> </span>
                        )}
                      </div>

                      <div className="mt-1 flex min-h-0 flex-1 gap-1.5">
                        <textarea
                          className="min-h-0 min-w-0 flex-1 resize-none overflow-y-auto rounded-lg border border-slate-200 bg-white p-2 text-sm leading-snug outline-none placeholder:text-slate-400/85 placeholder:text-left focus:border-sky-400 focus:ring-1 focus:ring-sky-400/25 read-only:bg-slate-50 read-only:text-slate-700"
                          placeholder={STAGE_WRITING_HINT[stage]}
                          value={oridDisplay.stages[stage].d1}
                          readOnly={oridReadOnly}
                          onFocus={() => setFocusStage(stage)}
                          onChange={
                            oridReadOnly
                              ? undefined
                              : (e) =>
                                  setWritingData((prev) => ({
                                    ...prev,
                                    stages: {
                                      ...prev.stages,
                                      [stage]: { ...prev.stages[stage], d1: e.target.value },
                                    },
                                  }))
                          }
                        />
                        <div className="flex w-[34%] min-w-[5.75rem] max-w-[9.5rem] shrink-0 flex-col overflow-y-auto rounded-lg bg-sky-50/70 px-1.5 py-1.5 text-xs leading-snug text-slate-600 sm:w-[32%] sm:min-w-[6.5rem] sm:max-w-[10.5rem] sm:px-2 sm:text-sm sm:leading-snug">
                          <div className="mb-1 shrink-0 text-xs font-semibold text-slate-700 sm:text-sm">可以這樣開頭：</div>
                          <div className="flex flex-col gap-1">
                            {STAGE_SCAFFOLD_LINES[stage].map((line, idx) => (
                              <div key={line} className="flex gap-1 break-words">
                                <span className="shrink-0 font-medium text-slate-700">{idx + 1}.</span>
                                <span>{line}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="shrink-0 border-t border-slate-100 px-3 pb-2 pt-1.5 sm:px-3 sm:pb-3">
              <div className="flex flex-col gap-2">
                {weekNum === 2 && w2Phase === "orid_review" ? (
                  <button
                    type="button"
                    className="kid-btn-primary w-full py-2 text-sm sm:text-base"
                    disabled={!sessionId || !readingId || writingSubmitting}
                    onClick={() => void submitWeek2PhaseToSynthesis()}
                  >
                    ⏭️ 進入整合寫作
                  </button>
                ) : (
                  <div className="flex flex-col gap-1.5 sm:flex-row">
                    {weekNum === 1 ? (
                      <button
                        type="button"
                        className="kid-btn-secondary w-full py-2 text-sm sm:text-base"
                        disabled={!sessionId || writingSubmitting}
                        onClick={() => saveWriting("draft")}
                      >
                        {writingSubmitting ? "儲存中…" : "📝 儲存草稿"}
                      </button>
                    ) : null}
                    <button
                      type="button"
                      className="kid-btn-primary w-full py-2 text-sm sm:text-base"
                      disabled={!sessionId || !readingId || writingSubmitting}
                      onClick={() => saveWriting("submit")}
                    >
                      {writingSubmitting ? "儲存中…" : "💾 儲存並提交我的寫作"}
                    </button>
                  </div>
                )}
              </div>
              {fbError && <div className="mt-1.5 text-xs text-red-600 whitespace-pre-wrap sm:text-sm">{fbError}</div>}
              {encourageMsg && <div className="mt-1.5 text-xs font-medium text-sky-700 sm:text-sm">{encourageMsg}</div>}
              {saveMsg && <div className="mt-1.5 text-xs font-medium text-emerald-600 sm:text-sm">{saveMsg}</div>}
              {writingError && <div className="mt-1.5 text-xs text-red-600 whitespace-pre-wrap sm:text-sm">{writingError}</div>}
            </div>
          </div>
        </div>

        {showSynthesisColumn ? (
          <div className="kid-shell order-2 flex h-full min-h-0 flex-col overflow-hidden">
            <div className="kid-section-header shrink-0 justify-between">
              <div className="flex items-center gap-2">
                <span className="text-lg">🔗</span>
                <span className="text-sm font-bold">整合寫作</span>
              </div>
            </div>
            <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-hidden p-2">
              <textarea
                className="min-h-0 w-full flex-1 resize-none rounded-xl border border-slate-200 bg-white p-3 text-sm leading-relaxed outline-none focus:border-sky-400 focus:ring-1 focus:ring-sky-400/25"
                placeholder="在這裡撰寫整合稿…（怎麼寫可參考右側聊天室開場說明）"
                value={writingData.synthesis_draft ?? ""}
                onChange={(e) =>
                  setWritingData((prev) => ({
                    ...prev,
                    synthesis_draft: e.target.value,
                  }))
                }
              />
              <button
                type="button"
                className="kid-btn-primary shrink-0"
                disabled={!sessionId || fbLoading}
                onClick={() => void runSynthesisFeedback()}
              >
                {fbLoading ? "…" : "取得整合回饋"}
              </button>
            </div>
          </div>
        ) : null}

        <div className="kid-shell order-3 flex h-full min-h-0 flex-col overflow-hidden md:h-full">
          <div className="kid-section-header shrink-0">
            <span className="text-lg">💬</span>
            <span className="text-sm font-bold">寫作回饋夥伴</span>
          </div>

          <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-gradient-to-b from-slate-50 to-white">
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-y-contain p-2 sm:p-3">
              {messages.length === 0 ? (
                <div className="flex min-h-full flex-col items-center justify-center px-2 py-3 text-center text-xs text-slate-400 sm:text-sm">
                  {!historyLoaded
                    ? "載入中…"
                    : seededInitial && !readingContentReady
                      ? "載入教材中…"
                      : awaitingFirstAiBubble
                        ? "正在準備開場…"
                        : "尚無訊息"}
                </div>
              ) : (
                <div className="flex flex-col gap-2">
                  {messages.map((m, idx) => {
                    const isStudent = m.role === "student";
                    const parsedFeedback = !isStudent ? parseFeedbackNarration(m.text) : null;
                    return (
                      <div
                        key={idx}
                        className={["flex items-end gap-2", isStudent ? "justify-end" : "justify-start"].join(" ")}
                      >
                        {!isStudent && (
                          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-sky-100 text-sm shadow-sm">
                            🤖
                          </div>
                        )}
                        {parsedFeedback ? (
                          <FeedbackGuideCard parsed={parsedFeedback} />
                        ) : (
                          <div
                            className={["max-w-[min(92%,28rem)]", isStudent ? "kid-bubble-student" : "kid-bubble-ai"].join(
                              " ",
                            )}
                          >
                            <div className="whitespace-pre-wrap leading-relaxed">{m.text}</div>
                          </div>
                        )}
                        {isStudent && (
                          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-sky-100 text-sm shadow-sm">
                            🧒
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
              <div
                className="shrink-0 border-t border-sky-100/70 bg-sky-50/95 px-2 py-2 sm:px-3"
                aria-live="polite"
                aria-label="機器人正在輸入"
              >
                <div className="flex items-end gap-2 justify-start">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-sky-100 text-sm shadow-sm">
                    🤖
                  </div>
                  <div className="max-w-[min(92%,28rem)] kid-bubble-ai">
                    <div className="flex items-center gap-1.5 py-1">
                      <span className="h-2 w-2 rounded-full bg-sky-400/80 animate-bounce [animation-delay:-0.24s]" />
                      <span className="h-2 w-2 rounded-full bg-sky-400/80 animate-bounce [animation-delay:-0.12s]" />
                      <span className="h-2 w-2 rounded-full bg-sky-400/80 animate-bounce" />
                      <span className="ml-2 text-xs text-slate-500 sm:text-sm">正在思考中…</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="shrink-0 border-t border-slate-200 bg-slate-50/80 px-2 py-1.5 text-center text-[10px] text-slate-500 sm:px-3 sm:py-2 sm:text-xs">
            {showStageFeedbackButtons
              ? "點左側任一格的「取得回饋」，回覆會出現在這裡。"
              : showSynthesisColumn
                ? "整合稿寫在中欄；按「取得整合回饋」後，教練回覆會出現在這裡。"
                : "請用右側對話與寫作教練聊聊。"}
          </div>
        </div>
      </div>
    </div>
  );
}
