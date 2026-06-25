"use client";

import { useParams } from "next/navigation";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { BookHelperAvatar } from "@/components/orid/BookIllustration";
import { FeedbackGuideCard } from "@/components/orid/FeedbackGuideCard";
import { OridWeekHero } from "@/components/orid/OridWeekHero";
import { OridPartnerMascot } from "@/components/orid/OridMascotImage";
import { PersimmonBullet } from "@/components/orid/PersimmonBullet";
import { getBookWeekArt } from "@/lib/orid-book-art";
import {
  DRAFT_SAVE_ENCOURAGEMENT,
  STAGE_MISSION_META,
  SUBMIT_ALL_DONE_ENCOURAGEMENT,
  SUBMIT_PARTIAL_ENCOURAGEMENT,
} from "@/lib/orid-mission-copy";
import { ORID_UNLOCKED_WEEKS } from "@/lib/orid-week-access";
import { ORID_STAGE_THEME } from "@/lib/orid-stage-theme";
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
  const missionProgress = useMemo(() => {
    const data = weekNum === 2 ? (week1Data ?? createEmptyWriting(1)) : writingData;
    return STAGES.map(({ key }) => ({
      stage: key,
      status: deriveStageMissionStatus(data.stages[key]),
    }));
  }, [writingData, week1Data, weekNum]);
  const writtenCount = useMemo(
    () => missionProgress.filter((item) => item.status !== "not_started").length,
    [missionProgress],
  );
  const allStagesWritten = useMemo(
    () => STAGES.every(({ key }) => String(writingData.stages[key].d1 ?? "").trim().length > 0),
    [writingData],
  );

  const mainGridClass = showSynthesisColumn
    ? "grid min-h-0 w-full flex-1 grid-cols-1 gap-2.5 overflow-hidden md:grid-cols-[1fr_1fr] md:gap-3 xl:grid-cols-[1fr_1fr_1fr]"
    : "grid min-h-0 w-full flex-1 grid-cols-1 gap-2.5 overflow-hidden md:grid-cols-[1fr_1fr] md:gap-3";

  const aiPartnerShellClass = showSynthesisColumn
    ? "kid-shell order-3 flex min-h-0 w-full min-w-0 flex-col overflow-hidden max-md:min-h-[35vh] md:order-2 md:col-start-2 md:h-full md:row-start-1 xl:order-3 xl:col-start-3"
    : "kid-shell order-3 flex min-h-0 w-full min-w-0 flex-col overflow-hidden max-md:min-h-[35vh] md:order-2 md:col-start-2 md:h-full md:row-start-1";

  const activeStageDef = STAGES.find((s) => s.key === focusStage) ?? STAGES[0];
  const activeStage = activeStageDef.key;
  const activeTheme = ORID_STAGE_THEME[activeStage];
  const activeStageStatus = deriveStageMissionStatus(oridDisplay.stages[activeStage]);
  const activeMissionMeta = STAGE_MISSION_META[activeStage];
  const activeAiExample = oridDisplay.stages[activeStage].feedback?.d1?.example?.trim();
  const activeCardMeta = STAGE_CARD_META[activeStage];

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

  return (
    <div className="flex h-full min-h-0 w-full flex-1 flex-col overflow-hidden">
      <div className={mainGridClass}>
        <div className="order-1 flex min-h-0 w-full min-w-0 flex-col gap-2.5 overflow-hidden md:h-full md:min-h-0">
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
          />

          <div className="kid-shell flex min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden max-md:min-h-[40vh]">
            {weekNum === 2 ? (
              <div className="shrink-0 border-b border-amber-100 px-3 py-1.5 text-right text-[10px] text-amber-900/70 sm:text-xs">
                {w2Phase === "orid_review" ? "顯示第 1 週已儲存內容（唯讀）" : "第 1 週四段（唯讀）"}
              </div>
            ) : null}

            <div className="flex min-h-0 w-full flex-1 flex-col p-2">
              <div
                className={[
                  "relative flex min-h-0 w-full flex-1 flex-col overflow-hidden rounded-2xl border-2 border-t-4 bg-white shadow-sm transition-all",
                  activeTheme.topBorder,
                  activeTheme.cardFocus,
                ].join(" ")}
              >
                <div className="flex shrink-0 items-start justify-between gap-2 px-2.5 pb-1 pt-2 sm:px-3">
                  <div className="min-w-0">
                    <div className={`text-xs font-bold sm:text-sm ${activeTheme.titleColor}`}>
                      {weekNum === 1 ? activeCardMeta.title : STAGE_TITLES[activeStage]}
                    </div>
                    <div className="text-[11px] leading-snug text-amber-900/65 sm:text-xs">
                      {weekNum === 1 ? activeCardMeta.question : STAGE_WRITING_HINT[activeStage]}
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
                  {showStageFeedbackButtons ? (
                    <button
                      type="button"
                      className={activeTheme.btnClass}
                      disabled={!sessionId || fbLoading}
                      onClick={() => runFeedback(activeStage)}
                    >
                      {fbLoading ? "…" : "取得回饋"}
                    </button>
                  ) : null}
                </div>

                <div className="relative flex min-h-0 flex-1 flex-col px-2 pt-0 sm:px-2.5">
                  {weekNum === 1 ? (
                    <div className="mb-1 shrink-0 text-[10px] text-amber-900/60 sm:text-[11px]">
                      {activeMissionMeta.helperHint}
                    </div>
                  ) : null}

                  <div className="flex min-h-0 flex-1 gap-1.5">
                    <textarea
                      className={[
                        "min-h-[12rem] min-w-0 flex-1 resize-none overflow-y-auto rounded-xl border border-amber-100 bg-[#fffcf7] p-2.5 text-[15px] leading-relaxed outline-none placeholder:text-amber-900/35 focus:ring-2 read-only:bg-amber-50/40 md:min-h-0",
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
                    <div
                      className={[
                        "flex w-[34%] min-w-[6rem] shrink-0 flex-col overflow-y-auto rounded-xl border p-1.5 text-[11px] leading-snug sm:w-[32%] sm:min-w-[7rem] sm:p-2 sm:text-xs md:w-[30%] md:max-w-none lg:w-[28%]",
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
                  </div>
                </div>
              </div>
            </div>

            <div className="shrink-0 border-t border-amber-100 px-3 pb-2.5 pt-2">
              <div className="flex flex-col gap-2">
                {weekNum === 2 && w2Phase === "orid_review" ? (
                  <button
                    type="button"
                    className="kid-btn-primary w-full"
                    disabled={!sessionId || !readingId || writingSubmitting}
                    onClick={() => void submitWeek2PhaseToSynthesis()}
                  >
                    ⏭️ 進入整合寫作
                  </button>
                ) : (
                  <div className="flex flex-col gap-2 sm:flex-row">
                    {weekNum === 1 ? (
                      <button
                        type="button"
                        className="kid-btn-secondary w-full sm:flex-1"
                        disabled={!sessionId || writingSubmitting}
                        onClick={() => saveWriting("draft")}
                      >
                        {writingSubmitting ? "儲存中…" : "📝 儲存草稿"}
                      </button>
                    ) : null}
                    <button
                      type="button"
                      className="kid-btn-primary w-full sm:flex-[1.4]"
                      disabled={!sessionId || !readingId || writingSubmitting}
                      onClick={() => saveWriting("submit")}
                    >
                      {writingSubmitting ? "儲存中…" : "🌰 儲存並提交我的寫作"}
                    </button>
                  </div>
                )}
              </div>
              {fbError && <div className="mt-1.5 whitespace-pre-wrap text-xs text-red-600 sm:text-sm">{fbError}</div>}
              {encourageMsg && <div className="mt-1.5 text-xs font-medium text-amber-800 sm:text-sm">{encourageMsg}</div>}
              {saveMsg && <div className="mt-1.5 text-xs font-medium text-emerald-600 sm:text-sm">{saveMsg}</div>}
              {writingError && <div className="mt-1.5 whitespace-pre-wrap text-xs text-red-600 sm:text-sm">{writingError}</div>}
            </div>
          </div>
        </div>

        {showSynthesisColumn ? (
          <div className="kid-shell order-2 flex min-h-0 w-full min-w-0 flex-col overflow-hidden max-md:min-h-[30vh] md:order-3 md:col-span-2 xl:order-2 xl:col-span-1 xl:h-full">
            <div className="kid-section-header-partner">
              <span className="text-sm font-bold text-amber-950">整合寫作</span>
            </div>
            <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-hidden p-2">
              <textarea
                className="min-h-0 w-full flex-1 resize-none rounded-xl border border-amber-100 bg-[#fffcf7] p-3 text-base leading-relaxed outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-300/30"
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

        <div className={aiPartnerShellClass}>
          <div className="kid-section-header-partner">
            <div className="text-sm font-bold text-amber-950 sm:text-base">AI 小幫手的回饋夥伴</div>
          </div>

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
              {messages.length === 0 ? (
                <div className="flex h-full min-h-[6rem] items-center justify-center px-2 text-center text-xs text-amber-900/50 sm:text-sm">
                  {!historyLoaded
                    ? "載入中…"
                    : seededInitial && !readingContentReady
                      ? "載入教材中…"
                      : awaitingFirstAiBubble
                        ? "小幫手正在準備開場…"
                        : "還沒有回饋訊息，先去寫作吧！"}
                </div>
              ) : (
                <div className="flex flex-col gap-3">
                  {messages.map((m, idx) => {
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
        </div>
      </div>
    </div>
  );
}
