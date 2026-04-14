"use client";

import { useParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

type ChatMsg = { role: "student" | "ai"; text: string };

type StageKey = "O" | "R" | "I" | "D";
type DraftKey = "d1" | "d2";
type ConditionKey = "genai" | "template" | "control";

type WritingFeedback = {
  ok: boolean;
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

type OridWritingV1 = {
  schema: "orid_writing_v1";
  week: number;
  stages: Record<StageKey, OridWritingStage>;
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

const STAGES: { key: StageKey; label: string }[] = [
  { key: "O", label: "O (Objective)" },
  { key: "R", label: "R (Reflective)" },
  { key: "I", label: "I (Interpretive)" },
  { key: "D", label: "D (Decisional)" },
];

const STAGE_TITLES: Record<StageKey, string> = {
  O: "O 客觀事實",
  R: "R 感受與原因",
  I: "I 意義／價值推論",
  D: "D 行動決策",
};

const STAGE_PLACEHOLDER: Record<StageKey, string> = {
  O: "請描述故事發生了什麼…",
  R: "我感到…因為…",
  I: "這代表什麼？我重視的價值是…",
  D: "我打算…在…情境採取…",
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
  return {
    schema: "orid_writing_v1",
    week,
    stages: {
      O: { d1: "", d2: "" },
      R: { d1: "", d2: "" },
      I: { d1: "", d2: "" },
      D: { d1: "", d2: "" },
    },
  };
}

function normalizeFeedbackObject(input: any): WritingFeedback | null {
  if (!input || typeof input !== "object") return null;
  return {
    ok: !!input.ok,
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

  return {
    schema: "orid_writing_v1",
    week: Number(obj?.week ?? week) || week,
    stages,
  };
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

function buildCoachWelcomeMsg(bookPack: BookPackV1 | null): ChatMsg {
  const title = String(bookPack?.book_title ?? "").trim();
  const book = title ? `《${title}》` : "這本書";
  return {
    role: "ai",
    text: `先從左邊任一格開始寫都可以喔！這裡是 ${book} 的 ORID 反思。寫一寫若卡住，按該格的「取得回饋」，我就會在這裡幫你看。`,
  };
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

  if (!weekStr || Number.isNaN(weekNum)) return <div className="p-6">週次格式不正確</div>;
  if (weekNum !== 1) return <div className="p-6">目前只開放第 1 週測試</div>;

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

  const [draftView, setDraftView] = useState<DraftKey>("d1");
  const [focusStage, setFocusStage] = useState<StageKey>("O");
  const [fbLoading, setFbLoading] = useState(false);
  const [fbError, setFbError] = useState<string | null>(null);

  const awaitingFirstAiBubble =
    !!sessionId &&
    historyLoaded &&
    seededInitial &&
    readingContentReady &&
    messages.length === 0;

  const showAiTyping = !!sessionId && fbLoading;

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, showAiTyping]);

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
    if (!res.ok) throw new Error(`ensure 失敗：${res.status} ${text}`);
    return text ? JSON.parse(text) : null;
  }

  async function restartWeek() {
    try {
      setLoading(true);
      setError(null);

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
      setFbError(null);
      setSaveMsg(null);
      setFocusStage("O");
      setDraftView("d1");

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
          setWritingData(createEmptyWriting(weekNum));
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

  /** 尚無訊息時插入寫作教練開場（等教材載入以顯示書名）。 */
  useEffect(() => {
    if (!seededInitial || !readingContentReady) return;
    setMessages((prev) => {
      if (prev.length > 0) return prev;
      return [buildCoachWelcomeMsg(bookPack)];
    });
  }, [seededInitial, readingContentReady, bookPack]);

  async function reloadChatHistorySafely(activeSessionId: string) {
    const res = await fetch(`/api/orid/messages?session_id=${activeSessionId}&order=asc&limit=200`, {
      method: "GET",
      cache: "no-store",
    });
    if (!res.ok) return;
    const list = await res.json().catch(() => []);
    const mapped: ChatMsg[] = Array.isArray(list)
      ? list.map(toChatMsg).filter((x): x is ChatMsg => x !== null)
      : [];
    if (mapped.length) setMessages(mapped);
  }

  async function runFeedback(stage: StageKey, draft: DraftKey) {
    if (!sessionId) return;

    const text = String(writingData.stages[stage]?.[draft] ?? "").trim();
    if (!text) {
      setFbError("請先寫一些內容再取得回饋。");
      return;
    }

    try {
      setFbLoading(true);
      setFbError(null);

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
      if (!r.ok) throw new Error(`回饋失敗：${r.status} ${raw}`);

      const data = raw ? JSON.parse(raw) : {};
      const outStage = coerceStageKey(data?.stage, stage);
      const outDraft: DraftKey = normalizeDraftKey(data?.meta?.draft ?? data?.draft, draft);

      const normalizedCondition = String(data?.meta?.condition ?? condition).toLowerCase();
      const fb: WritingFeedback = {
        ok: !!data?.feedback_ok,
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

      const savedId = String(data?.meta?.saved_to_writing_id ?? "");
      if (isUuid(savedId)) setWritingId(savedId);
      await reloadChatHistorySafely(sessionId);
    } catch (e: any) {
      setFbError(e?.message ?? "回饋失敗");
    } finally {
      setFbLoading(false);
    }
  }

  async function saveWriting(label: "draft" | "submit") {
    if (!sessionId || !readingId) return;

    try {
      setWritingSubmitting(true);
      setWritingError(null);
      setSaveMsg(null);

      const content = JSON.stringify(writingData);
      const isUpdate = isUuid(writingId);
      const method = isUpdate ? "PUT" : "POST";
      const body = isUpdate
        ? { id: writingId, content }
        : { reading_id: readingId, session_id: sessionId, week: weekNum, content };

      const r = await fetch(`/api/orid/writings`, {
        method,
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const text = await r.text();
      if (!r.ok) throw new Error(text || `寫作送出失敗（${r.status}）`);

      const data = text ? JSON.parse(text) : null;
      if (isUuid(data?.id)) setWritingId(String(data.id));

      setSaveMsg(label === "draft" ? "已儲存草稿 ✅" : "已提交 ✅（示範：同樣會儲存到 DB）");
    } catch (e: any) {
      setWritingError(e?.message ?? "儲存失敗");
    } finally {
      setWritingSubmitting(false);
    }
  }

  const PANEL_H =
    "min-h-[min(42vh,280px)] max-h-[min(72vh,780px)] h-[calc(100vh-13rem)] sm:h-[calc(100vh-11.5rem)] md:h-[calc(100vh-12rem)]";

  const STAGE_COLORS: Record<StageKey, string> = {
    O: "from-sky-400 to-sky-500",
    R: "from-amber-400 to-orange-500",
    I: "from-emerald-400 to-teal-500",
    D: "from-violet-400 to-purple-500",
  };

  const STAGE_EMOJI: Record<StageKey, string> = { O: "👀", R: "💭", I: "💡", D: "🎯" };

  return (
    <div className="space-y-5">
      {/* Hero banner */}
      <div className="rounded-2xl bg-gradient-to-r from-sky-500 to-blue-600 px-8 py-6 text-white shadow-lg sm:px-10">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold sm:text-3xl">📖 AI–ORID 反思寫作</h1>
            <p className="mt-1 text-base text-sky-100">
              第 {weekNum} 週｜先寫作（左）→ 回饋夥伴（右）
              {bookPack?.book_title ? `｜${bookPack.book_title}` : ""}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {loading ? (
              <span className="text-sm text-sky-200">初始化中…</span>
            ) : error ? (
              <span className="rounded-lg bg-red-500/20 px-3 py-1 text-sm text-white">{error}</span>
            ) : (
              <span className="rounded-full bg-white/20 px-3 py-1 text-xs backdrop-blur-sm">{condition}</span>
            )}
            <button
              type="button"
              onClick={restartWeek}
              disabled={loading}
              className="rounded-xl bg-white/20 px-4 py-2 text-sm font-medium backdrop-blur-sm transition hover:bg-white/30 disabled:opacity-50"
              title="開新 session、清空聊天與寫作（demo 用）"
            >
              重新開始本週
            </button>
          </div>
        </div>

        {/* 四格皆可寫；高亮目前關注的寫作區（點格子或輸入時可切換） */}
        <div className="mt-4 flex flex-wrap gap-2">
          {STAGES.map((s) => {
            const active = focusStage === s.key;
            return (
              <button
                key={s.key}
                type="button"
                onClick={() => setFocusStage(s.key)}
                className={[
                  "inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-[15px] font-medium transition-all",
                  active ? "bg-white text-sky-700 shadow-md" : "bg-white/15 text-sky-100 hover:bg-white/25",
                ].join(" ")}
              >
                <span>{STAGE_EMOJI[s.key]}</span>
                {s.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* 平板 md 起雙欄；手機直向先寫作再聊天 */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 md:gap-5">
        <div className="kid-shell flex min-h-0 flex-col overflow-hidden md:order-1">
          <div className="kid-section-header justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xl">✍️</span>
              <span className="text-base font-bold">反思寫作</span>
            </div>
            <div className="flex shrink-0 gap-1.5">
              {(["d1", "d2"] as DraftKey[]).map((dk) => (
                <button
                  key={dk}
                  className={[
                    "rounded-full px-3 py-1 text-xs font-medium transition-all",
                    draftView === dk ? "bg-white text-sky-700 shadow" : "bg-white/20 text-sky-100 hover:bg-white/30",
                  ].join(" ")}
                  onClick={() => setDraftView(dk)}
                  type="button"
                >
                  {dk === "d1" ? "草稿 1" : "草稿 2"}
                </button>
              ))}
            </div>
          </div>

          <div className={`${PANEL_H} flex-1 overflow-auto`}>
            <div className="grid grid-cols-1 gap-3 p-3 sm:gap-4 sm:p-4 md:grid-cols-2">
              {STAGES.map((s) => {
                const stage = s.key;
                const isFocused = focusStage === stage;

                return (
                  <div
                    key={stage}
                    className={[
                      "flex min-h-0 flex-col rounded-xl border p-3 sm:p-4",
                      isFocused
                        ? "border-sky-300 bg-sky-50/40 shadow-sm ring-1 ring-sky-200"
                        : "border-slate-200 bg-white hover:border-sky-200",
                    ].join(" ")}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex min-w-0 items-center gap-2">
                        <span
                          className={`inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br ${STAGE_COLORS[stage]} text-sm text-white`}
                        >
                          {STAGE_EMOJI[stage]}
                        </span>
                        <span className="text-[14px] font-bold leading-tight text-slate-700 sm:text-[15px]">
                          {STAGE_TITLES[stage]}
                        </span>
                      </div>
                      <button
                        type="button"
                        className="kid-btn-primary shrink-0 !px-2.5 !py-1 !text-xs"
                        disabled={!sessionId || fbLoading}
                        onClick={() => runFeedback(stage, draftView)}
                      >
                        {fbLoading ? "…" : "取得回饋"}
                      </button>
                    </div>

                    <textarea
                      className="mt-2 min-h-[72px] w-full flex-1 rounded-lg border border-slate-200 bg-white p-2.5 text-[15px] leading-relaxed outline-none placeholder:text-slate-400 focus:border-sky-400 focus:ring-2 focus:ring-sky-400/20 sm:min-h-[88px] sm:p-3 md:min-h-[100px]"
                      placeholder={STAGE_PLACEHOLDER[stage]}
                      value={writingData.stages[stage][draftView]}
                      onFocus={() => setFocusStage(stage)}
                      onChange={(e) =>
                        setWritingData((prev) => ({
                          ...prev,
                          stages: {
                            ...prev.stages,
                            [stage]: { ...prev.stages[stage], [draftView]: e.target.value },
                          },
                        }))
                      }
                    />
                  </div>
                );
              })}
            </div>

            <div className="border-t border-slate-100 px-3 pb-3 pt-2 sm:px-4 sm:pb-4">
              <div className="flex flex-col gap-2 sm:flex-row sm:gap-3">
                <button
                  type="button"
                  className="kid-btn-secondary w-full flex-1 sm:w-auto"
                  disabled={!sessionId || !readingId || writingSubmitting}
                  onClick={() => saveWriting("draft")}
                >
                  💾 儲存草稿
                </button>
                <button
                  type="button"
                  className="kid-btn-primary w-full flex-1 sm:w-auto"
                  disabled={!sessionId || !readingId || writingSubmitting}
                  onClick={() => saveWriting("submit")}
                >
                  ✅ 提交
                </button>
              </div>
              {fbError && <div className="mt-2 text-sm text-red-600 whitespace-pre-wrap">{fbError}</div>}
              {saveMsg && <div className="mt-2 text-sm font-medium text-emerald-600">{saveMsg}</div>}
              {writingError && <div className="mt-2 text-sm text-red-600 whitespace-pre-wrap">{writingError}</div>}
            </div>
          </div>
        </div>

        <div className="kid-shell flex min-h-0 flex-col overflow-hidden md:order-2">
          <div className="kid-section-header">
            <span className="text-xl">💬</span>
            <span className="text-base font-bold">寫作回饋夥伴</span>
          </div>

          <div
            className={`${PANEL_H} flex-1 overflow-auto bg-gradient-to-b from-slate-50 to-white p-4 sm:p-5 space-y-3`}
          >
            {messages.length === 0 ? (
              <div className="flex h-full min-h-[12rem] items-center justify-center px-2 text-center text-sm text-slate-400">
                {!historyLoaded
                  ? "載入中…"
                  : seededInitial && !readingContentReady
                    ? "載入教材中…"
                    : awaitingFirstAiBubble
                      ? "正在準備開場…"
                      : "尚無訊息"}
              </div>
            ) : (
              messages.map((m, idx) => {
                const isStudent = m.role === "student";
                return (
                  <div
                    key={idx}
                    className={["flex items-end gap-2.5", isStudent ? "justify-end" : "justify-start"].join(" ")}
                  >
                    {!isStudent && (
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-sky-100 text-base shadow-sm">
                        🤖
                      </div>
                    )}
                    <div
                      className={["max-w-[min(92%,28rem)]", isStudent ? "kid-bubble-student" : "kid-bubble-ai"].join(
                        " ",
                      )}
                    >
                      <div className="whitespace-pre-wrap text-[15px] leading-relaxed">{m.text}</div>
                    </div>
                    {isStudent && (
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-sky-100 text-base shadow-sm">
                        🧒
                      </div>
                    )}
                  </div>
                );
              })
            )}
            {showAiTyping && (
              <div className="flex items-end gap-2.5 justify-start" aria-live="polite" aria-label="機器人正在輸入">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-sky-100 text-base shadow-sm">
                  🤖
                </div>
                <div className="max-w-[min(92%,28rem)] kid-bubble-ai">
                  <div className="flex items-center gap-1.5 py-1">
                    <span className="h-2 w-2 rounded-full bg-sky-400/80 animate-bounce [animation-delay:-0.24s]" />
                    <span className="h-2 w-2 rounded-full bg-sky-400/80 animate-bounce [animation-delay:-0.12s]" />
                    <span className="h-2 w-2 rounded-full bg-sky-400/80 animate-bounce" />
                    <span className="ml-2 text-xs text-slate-500">正在思考中…</span>
                  </div>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          <div className="border-t border-slate-200 bg-slate-50/80 px-4 py-3 text-center text-xs text-slate-500">
            點左側任一格的「取得回饋」，回覆會出現在這裡（目前：{draftView === "d1" ? "草稿 1" : "草稿 2"}）。
          </div>
        </div>
      </div>
    </div>
  );
}
