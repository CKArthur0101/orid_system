"use client";

import { useParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";

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

type FeedbackState = Partial<Record<StageKey, Partial<Record<DraftKey, WritingFeedback>>>>;

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

const DEFAULT_HINTS_BY_STAGE: Record<StageKey, string[]> = {
  O: [
    "回想剛剛聊到的角色、事情和順序",
    "可以用「先…後來…最後…」來整理",
    "先寫故事裡真的發生的事，不要先加感想",
  ],
  R: [
    "想一想你最明顯的感受是什麼",
    "可以用「我感到…因為…」開頭",
    "把感受和故事中的原因連在一起",
  ],
  I: [
    "想一想這個故事提醒了你什麼",
    "可以用「我覺得這代表…因為…」來寫",
    "把你的想法和故事內容連起來",
  ],
  D: [
    "想一想下次遇到類似情況你會怎麼做",
    "可以用「下次我會…」開頭",
    "行動要寫得具體、真的做得到",
  ],
};

function idxOfStage(s: string) {
  return STAGES.findIndex((x) => x.key === s);
}

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

function sanitizeOneQuestion(text: string): string {
  const t = (text || "").replaceAll("?", "？").trim();
  if (!t) return "你可以再說清楚一點嗎？";
  if (!t.includes("？")) return t + "？";
  const first = t.split("？")[0].trim();
  return first + "？";
}

function normalizeHints(input: unknown, stage: StageKey): string[] {
  if (Array.isArray(input)) {
    const arr = input.map((x) => String(x).trim()).filter(Boolean);
    if (arr.length > 0) return arr.slice(0, 3);
  }
  return DEFAULT_HINTS_BY_STAGE[stage];
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

function normalizeWritingContent(raw: unknown, week: number): { writing: OridWritingV1; feedback: FeedbackState } {
  const empty = createEmptyWriting(week);
  if (!raw || typeof raw !== "object") return { writing: empty, feedback: {} };

  const obj = raw as any;
  const stages: Record<StageKey, OridWritingStage> = {
    O: { d1: "", d2: "" },
    R: { d1: "", d2: "" },
    I: { d1: "", d2: "" },
    D: { d1: "", d2: "" },
  };
  const feedback: FeedbackState = {};

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

    if (d1fb || d2fb) {
      feedback[stage] = {
        ...(d1fb ? { d1: d1fb } : {}),
        ...(d2fb ? { d2: d2fb } : {}),
      };
    }
  }

  return {
    writing: {
      schema: "orid_writing_v1",
      week: Number(obj?.week ?? week) || week,
      stages,
    },
    feedback,
  };
}

function parseWritingRecordContent(content: unknown, week: number): { writing: OridWritingV1; feedback: FeedbackState } {
  if (!content) return { writing: createEmptyWriting(week), feedback: {} };

  if (typeof content === "object") {
    return normalizeWritingContent(content, week);
  }

  if (typeof content === "string") {
    try {
      return normalizeWritingContent(JSON.parse(content), week);
    } catch {
      return { writing: createEmptyWriting(week), feedback: {} };
    }
  }

  return { writing: createEmptyWriting(week), feedback: {} };
}

function buildInitialAiMsg(bookPack: BookPackV1 | null): ChatMsg {
  const title = String(bookPack?.book_title ?? "").trim();
  const events = Array.isArray(bookPack?.key_events) ? bookPack!.key_events!.map(String).filter(Boolean) : [];
  const firstEvent = String(events[0] ?? "").trim();
  const anchor = firstEvent.replaceAll("？", "").replaceAll("?", "").slice(0, 36);

  if (title && anchor) {
    return {
      role: "ai",
      text: sanitizeOneQuestion(`我們今天要聊《${title}》。故事一開始提到${anchor}你還記得後來接著發生了什麼`),
    };
  }

  if (title) {
    return {
      role: "ai",
      text: sanitizeOneQuestion(`我們今天要聊《${title}》。你還記得故事一開始發生了什麼嗎`),
    };
  }

  return {
    role: "ai",
    text: sanitizeOneQuestion("你還記得故事一開始發生了什麼嗎"),
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
  const [currentStage, setCurrentStage] = useState<string>("O");

  const [readingReloadNonce, setReadingReloadNonce] = useState(0);
  const [bookPack, setBookPack] = useState<BookPackV1 | null>(null);

  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [input, setInput] = useState("");
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
  const [fbState, setFbState] = useState<FeedbackState>({});

  const [stageHints, setStageHints] = useState<Partial<Record<StageKey, string[]>>>({});
  const [hintsLoading, setHintsLoading] = useState<Partial<Record<StageKey, boolean>>>({});
  const hintsFetchedRef = useRef<Record<string, boolean>>({});
  const hintsFetchingRef = useRef<Record<string, boolean>>({});

  const canChat = useMemo(() => !!sessionId && !loading, [sessionId, loading]);

  const unlockedIndex = useMemo(() => {
    const i = idxOfStage(currentStage || "O");
    return i < 0 ? 0 : i;
  }, [currentStage]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  useEffect(() => {
    const stage = coerceStageKey(currentStage, "O");
    if (idxOfStage(focusStage) > unlockedIndex) {
      setFocusStage(stage);
      setDraftView("d1");
    }
  }, [currentStage, unlockedIndex, focusStage]);

  useEffect(() => {
    if (!sessionId) return;

    const activeUnlocked = STAGES.slice(0, unlockedIndex + 1).map((s) => s.key);
    const ac = new AbortController();

    const fetchHintsForStage = async (stg: StageKey) => {
      const key = `${sessionId}:${stg}`;
      if (hintsFetchedRef.current[key]) return;
      if (hintsFetchingRef.current[key]) return;
      if (messages.length <= 2) return;

      try {
        hintsFetchingRef.current[key] = true;
        setHintsLoading((prev) => (prev[stg] ? prev : { ...prev, [stg]: true }));

        const res = await fetch(`/api/orid/writings/generate_hints`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessionId, stage: stg }),
          signal: ac.signal,
        });

        if (!res.ok) {
          setStageHints((prev) => {
            const nextHints = DEFAULT_HINTS_BY_STAGE[stg];
            const prevHints = prev[stg] ?? [];
            return prevHints.join("\n") === nextHints.join("\n") ? prev : { ...prev, [stg]: nextHints };
          });
          hintsFetchedRef.current[key] = true;
          return;
        }

        const data = await res.json();
        const nextHints = normalizeHints(data?.hints, stg);
        setStageHints((prev) => {
          const prevHints = prev[stg] ?? [];
          return prevHints.join("\n") === nextHints.join("\n") ? prev : { ...prev, [stg]: nextHints };
        });
        hintsFetchedRef.current[key] = true;
      } catch (err: any) {
        if (err?.name === "AbortError") return;
        setStageHints((prev) => {
          const nextHints = DEFAULT_HINTS_BY_STAGE[stg];
          const prevHints = prev[stg] ?? [];
          return prevHints.join("\n") === nextHints.join("\n") ? prev : { ...prev, [stg]: nextHints };
        });
        hintsFetchedRef.current[key] = true;
      } finally {
        delete hintsFetchingRef.current[key];
        setHintsLoading((prev) => (prev[stg] ? { ...prev, [stg]: false } : prev));
      }
    };

    activeUnlocked.forEach((stg) => {
      void fetchHintsForStage(stg);
    });

    return () => ac.abort();
  }, [unlockedIndex, sessionId, messages.length]);


  useEffect(() => {
    hintsFetchedRef.current = {};
    hintsFetchingRef.current = {};
    setStageHints({});
    setHintsLoading({});
  }, [sessionId]);

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
      setCurrentStage(s?.current_stage ? String(s.current_stage) : "O");

      setBookPack(null);
      setReadingReloadNonce((n) => n + 1);

      setHistoryLoaded(true);
      setChatError(null);
      setInput("");

      setWritingHydratedSessionId(null);
      setWritingId(null);
      setWritingData(emptyWriting);
      setFbState({});
      setStageHints({});
      setHintsLoading({});
      hintsFetchedRef.current = {};
      hintsFetchingRef.current = {};
      setFbError(null);
      setSaveMsg(null);
      setFocusStage("O");
      setDraftView("d1");

      setMessages([buildInitialAiMsg(null)]);
      setSeededInitial(true);
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
        if (s?.current_stage) setCurrentStage(String(s.current_stage));
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
          let finalMapped = mapped;
          let shouldSeed = false;
          if (mapped[0].role === "student") {
            finalMapped = [buildInitialAiMsg(null), ...mapped];
            shouldSeed = true;
          }
          setMessages(finalMapped);
          setSeededInitial(shouldSeed);
        } else {
          setMessages([buildInitialAiMsg(null)]);
          setSeededInitial(true);
        }
      } catch (e: any) {
        if (e?.name === "AbortError") return;
        setError(e?.message ?? "載入聊天紀錄失敗");
        setMessages((prev) => (prev.length ? prev : [buildInitialAiMsg(null)]));
        setSeededInitial(true);
      } finally {
        if (!ac.signal.aborted) setHistoryLoaded(true);
      }
    })();

    return () => ac.abort();
  }, [sessionId, historyLoaded]);

  useEffect(() => {
    if (!readingId) return;
    const ac = new AbortController();

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
          const { writing, feedback } = parseWritingRecordContent(latest.content, weekNum);
          setWritingData(writing);
          setFbState(feedback);
        } else {
          setWritingData(createEmptyWriting(weekNum));
          setFbState({});
        }
      } catch {
        setWritingId(null);
        setWritingData(createEmptyWriting(weekNum));
        setFbState({});
      } finally {
        if (!ac.signal.aborted) setWritingHydratedSessionId(sessionId);
      }
    })();

    return () => ac.abort();
  }, [sessionId, weekNum, writingHydratedSessionId]);

  useEffect(() => {
    if (!seededInitial || !bookPack) return;
    setMessages((prev) => {
      if (prev.length === 0) return prev;
      if (prev[0]?.role !== "ai") return prev;
      const copy = [...prev];
      copy[0] = buildInitialAiMsg(bookPack);
      return copy;
    });
  }, [bookPack, seededInitial]);

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

  async function sendChat() {
    if (!sessionId) return;
    const text = input.trim();
    if (!text) return;

    const prevStage = coerceStageKey(currentStage, "O");

    try {
      setChatLoading(true);
      setChatError(null);
      setSeededInitial(false);

      setMessages((prev) => [...prev, { role: "student", text }]);
      setInput("");

      const r = await fetch("/api/orid/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, student_text: text }),
      });

      const raw = await r.text();
      if (!r.ok) throw new Error(raw || `聊天失敗（${r.status}）`);
      const data = raw ? JSON.parse(raw) : {};

      setMessages((prev) => [...prev, { role: "ai", text: String(data.ai_reply ?? "") }]);
      if (data?.current_stage) {
        const nextStage = coerceStageKey(data.current_stage, prevStage);
        const stageJump = idxOfStage(nextStage) - idxOfStage(prevStage);
        if (stageJump > 1) {
          await reloadChatHistorySafely(sessionId);
          setCurrentStage(prevStage);
          setChatError("偵測到階段不同步，已重新同步聊天紀錄，請再送出一次。");
          return;
        }
        setCurrentStage(nextStage);
        if (idxOfStage(nextStage) > idxOfStage(prevStage)) {
          setFocusStage(nextStage);
          setDraftView("d1");
        }
      }
    } catch (e: any) {
      setChatError(e?.message ?? "聊天失敗");
    } finally {
      setChatLoading(false);
    }
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

      const payload = { session_id: sessionId, week: weekNum, stage, draft, text, save: true };

      const r = await fetch("/api/orid/writings/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload),
      });

      const raw = await r.text();
      if (!r.ok) throw new Error(`回饋失敗：${r.status} ${raw}`);

      const data = raw ? JSON.parse(raw) : {};
      const outStage = coerceStageKey(data?.stage, stage);
      const outDraft: DraftKey = normalizeDraftKey(data?.draft, draft);

      const normalizedCondition = String(data?.meta?.condition ?? condition).toLowerCase();
      const fb: WritingFeedback = {
        ok: !!data?.ok,
        missing: Array.isArray(data?.missing) ? data.missing.map(String) : [],
        suggestions: Array.isArray(data?.suggestions) ? data.suggestions.map(String) : [],
        example: isControlConditionValue(normalizedCondition) ? null : (data?.example ?? null),
        improved: data?.improved ?? null,
        meta: data?.meta ?? null,
      };

      setFbState((prev) => ({
        ...prev,
        [outStage]: { ...(prev[outStage] ?? {}), [outDraft]: fb },
      }));

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
    } catch (e: any) {
      setFbError(e?.message ?? "回饋失敗");
    } finally {
      setFbLoading(false);
    }
  }

  function applyImprovedToDraft2(stage: StageKey) {
    const fb = fbState?.[stage]?.d1;
    const improved = String(fb?.improved ?? "").trim();
    if (!improved) return;

    setWritingData((prev) => ({
      ...prev,
      stages: { ...prev.stages, [stage]: { ...prev.stages[stage], d2: improved } },
    }));
    setDraftView("d2");
    setFocusStage(stage);
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

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      if (!chatLoading) sendChat();
    }
  }

  const fbNow = fbState?.[focusStage]?.[draftView];
  const displayHints = stageHints[focusStage]?.length ? stageHints[focusStage]! : DEFAULT_HINTS_BY_STAGE[focusStage];

  const EMOTION = ["難過", "擔心", "生氣", "感動"] as const;
  const VALUES = ["責任", "同理", "公平", "合作"] as const;
  const FRAMES = ["我感到…因為…", "我認為…因為…", "下次我會…在…"] as const;

  const CHAT_H = "h-[calc(100vh-300px)] min-h-[480px] max-h-[800px]";
  const RIGHT_H = "h-[calc(100vh-300px)] min-h-[480px] max-h-[800px]";

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
            <h1 className="text-2xl font-bold sm:text-3xl">📖 AI–ORID 反思對話</h1>
            <p className="mt-1 text-base text-sky-100">
              第 {weekNum} 週｜閱讀 → ORID 對話 → 反思寫作
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

        {/* Stage progress pills */}
        <div className="mt-4 flex flex-wrap gap-2">
          {STAGES.map((s, i) => {
            const active = currentStage === s.key;
            const done = i < idxOfStage(currentStage || "O");
            return (
              <span
                key={s.key}
                className={[
                  "inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-[15px] font-medium transition-all",
                  active
                    ? "bg-white text-sky-700 shadow-md"
                    : done
                      ? "bg-white/30 text-white"
                      : "bg-white/10 text-sky-200",
                ].join(" ")}
              >
                <span>{STAGE_EMOJI[s.key]}</span>
                {s.label}
              </span>
            );
          })}
        </div>
      </div>

      {/* Main two-column layout */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* === LEFT: Chat === */}
        <div className="kid-shell flex flex-col overflow-hidden">
          <div className="kid-section-header">
            <span className="text-xl">💬</span>
            <span className="text-base font-bold">AI–ORID 反思對話</span>
          </div>

          <div className={`${CHAT_H} flex-1 overflow-auto bg-gradient-to-b from-slate-50 to-white p-5 space-y-3`}>
            {messages.length === 0 ? (
              <div className="flex h-full items-center justify-center text-sm text-slate-400">
                {historyLoaded ? "尚無訊息，開始聊天吧！" : "載入中…"}
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
                    <div className={["max-w-[78%]", isStudent ? "kid-bubble-student" : "kid-bubble-ai"].join(" ")}>
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
            <div ref={chatEndRef} />
          </div>

          <div className="border-t border-slate-200 bg-white p-4">
            <div className="flex items-center gap-2">
              <input
                className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-[15px] outline-none placeholder:text-slate-400 focus:border-sky-400 focus:ring-2 focus:ring-sky-400/30"
                placeholder={canChat ? "輸入你的回應…" : "初始化中…"}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={!canChat || chatLoading}
              />
              <button
                onClick={sendChat}
                disabled={!canChat || chatLoading || !input.trim()}
                className="kid-btn-primary whitespace-nowrap"
              >
                {chatLoading ? "送出中…" : "送出"}
              </button>
            </div>
            {chatError && <div className="mt-2 text-sm text-red-600 whitespace-pre-wrap">{chatError}</div>}
          </div>
        </div>

        {/* === RIGHT: Writing + hints === */}
        <div className="kid-shell flex flex-col overflow-hidden">
          <div className="kid-section-header justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xl">✍️</span>
              <span className="text-base font-bold">反思寫作</span>
            </div>
            <div className="flex gap-1.5">
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

          <div className={`${RIGHT_H} flex-1 overflow-auto`}>
            <div className="grid grid-cols-1 gap-5 p-5 xl:grid-cols-5">
              {/* Writing areas */}
              <div className="xl:col-span-3 space-y-4">
                {STAGES.map((s, i) => {
                  const locked = i > unlockedIndex;
                  const stage = s.key;
                  const isFocused = focusStage === stage;

                  return (
                    <div
                      key={stage}
                      className={[
                        "rounded-xl border p-4 transition-all",
                        locked
                          ? "border-slate-200 bg-slate-50 opacity-50"
                          : isFocused
                            ? "border-sky-300 bg-sky-50/40 shadow-sm ring-1 ring-sky-200"
                            : "border-slate-200 bg-white hover:border-sky-200",
                      ].join(" ")}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span
                            className={`inline-flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br ${STAGE_COLORS[stage]} text-sm text-white`}
                          >
                            {STAGE_EMOJI[stage]}
                          </span>
                          <span className="text-[15px] font-bold text-slate-700">{STAGE_TITLES[stage]}</span>
                        </div>
                        {!locked && (
                          <button
                            type="button"
                            className="rounded-lg p-1 text-slate-400 transition hover:bg-sky-50 hover:text-sky-600"
                            title="查看提示與回饋"
                            onClick={() => setFocusStage(stage)}
                          >
                            💡
                          </button>
                        )}
                      </div>

                      <textarea
                        className="mt-3 w-full min-h-[100px] rounded-lg border border-slate-200 bg-white p-3 text-[15px] leading-relaxed outline-none placeholder:text-slate-400 focus:border-sky-400 focus:ring-2 focus:ring-sky-400/20 disabled:bg-slate-100"
                        placeholder={STAGE_PLACEHOLDER[stage]}
                        disabled={locked}
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

                      {locked && (
                        <p className="mt-2 text-xs text-slate-400">🔒 先完成前面的對話再寫這一段喔</p>
                      )}
                    </div>
                  );
                })}

                {/* Save buttons */}
                <div className="flex gap-3 pt-1">
                  <button
                    type="button"
                    className="kid-btn-secondary flex-1"
                    disabled={!sessionId || !readingId || writingSubmitting}
                    onClick={() => saveWriting("draft")}
                  >
                    💾 儲存草稿
                  </button>
                  <button
                    type="button"
                    className="kid-btn-primary flex-1"
                    disabled={!sessionId || !readingId || writingSubmitting}
                    onClick={() => saveWriting("submit")}
                  >
                    ✅ 提交
                  </button>
                </div>
                {saveMsg && <div className="text-sm font-medium text-emerald-600">{saveMsg}</div>}
                {writingError && <div className="text-sm text-red-600 whitespace-pre-wrap">{writingError}</div>}
              </div>

              {/* Hints + Feedback sidebar */}
              <div className="xl:col-span-2 space-y-4">
                <h3 className="flex items-center gap-2 text-base font-bold text-slate-700">
                  <span className="inline-flex h-6 w-6 items-center justify-center rounded-lg bg-amber-100 text-xs">📝</span>
                  寫作支架提示
                </h3>

                {hintsLoading[focusStage] && (
                  <div className="animate-pulse rounded-xl border border-amber-200 bg-amber-50 p-3 text-center text-xs text-amber-700">
                    正在替你整理聊天重點…
                  </div>
                )}

                <div className="rounded-xl border border-amber-200 bg-gradient-to-br from-amber-50 to-orange-50/50 p-4">
                  <p className="mb-2 flex items-center gap-1.5 text-sm font-bold text-amber-800">
                    <span>💡</span> 你剛剛聊到的重點
                  </p>
                  <ul className="list-disc space-y-1 pl-4 text-sm leading-relaxed text-amber-900">
                    {displayHints.map((hint, idx) => (
                      <li key={idx}>{hint}</li>
                    ))}
                  </ul>
                </div>

                <div className="space-y-3">
                  <div>
                    <p className="mb-1.5 text-sm font-semibold text-slate-600">情緒詞彙</p>
                    <div className="flex flex-wrap gap-1.5">
                      {EMOTION.map((t) => (
                        <span key={t} className="kid-chip">{t}</span>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="mb-1.5 text-sm font-semibold text-slate-600">價值詞彙</p>
                    <div className="flex flex-wrap gap-1.5">
                      {VALUES.map((t) => (
                        <span key={t} className="kid-chip">{t}</span>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="mb-1.5 text-sm font-semibold text-slate-600">句型提示</p>
                    <div className="space-y-1.5">
                      {FRAMES.map((t, i) => (
                        <div key={i} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm leading-relaxed text-slate-600">
                          {t}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Feedback section */}
                <div className="rounded-xl border border-slate-200 bg-white p-4">
                  <div className="flex items-center justify-between gap-2">
                    <h4 className="text-[15px] font-bold text-slate-700">回饋（{STAGE_TITLES[focusStage]}）</h4>
                    <button
                      type="button"
                      className="kid-btn-primary !px-3 !py-1.5 !text-xs"
                      disabled={!sessionId || fbLoading}
                      onClick={() => runFeedback(focusStage, draftView)}
                    >
                      {fbLoading ? "回饋中…" : "取得回饋"}
                    </button>
                  </div>

                  {fbError && <div className="mt-2 text-sm text-red-600 whitespace-pre-wrap">{fbError}</div>}

                  {fbNow && (
                    <div className="mt-3 space-y-3 text-sm">
                      <div
                        className={[
                          "rounded-lg border px-3 py-2",
                          fbNow.ok ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-amber-200 bg-amber-50 text-amber-800",
                        ].join(" ")}
                      >
                        {fbNow.ok
                          ? "✅ 這一段已達到基本要求，可以再寫得更完整。"
                          : "⚠️ 這一段還可以再補強，看看下面的建議。"}
                      </div>

                      {fbNow.missing?.length > 0 && (
                        <div>
                          <p className="font-bold text-slate-700">缺漏</p>
                          <ul className="list-disc pl-4 text-slate-600">
                            {fbNow.missing.map((x, i) => <li key={i}>{x}</li>)}
                          </ul>
                        </div>
                      )}

                      {fbNow.suggestions?.length > 0 && (
                        <div>
                          <p className="font-bold text-slate-700">建議</p>
                          <ul className="list-disc pl-4 text-slate-600">
                            {fbNow.suggestions.map((x, i) => <li key={i}>{x}</li>)}
                          </ul>
                        </div>
                      )}

                      {!isControlConditionValue(fbNow.meta?.condition ?? condition) && String(fbNow.example ?? "").trim() && (
                        <div>
                          <p className="font-bold text-slate-700">示例參考</p>
                          <div className="mt-1 rounded-lg border border-slate-200 bg-slate-50 p-3 whitespace-pre-wrap leading-relaxed text-slate-600">
                            {fbNow.example}
                          </div>
                        </div>
                      )}

                      {String(fbNow.improved ?? "").trim() && (
                        <div>
                          <p className="font-bold text-slate-700">改寫版本</p>
                          <div className="mt-1 rounded-lg border border-emerald-200 bg-emerald-50 p-3 whitespace-pre-wrap leading-relaxed text-emerald-800">
                            {fbNow.improved}
                          </div>
                        </div>
                      )}

                      {!fbNow.missing?.length &&
                        !fbNow.suggestions?.length &&
                        !String(fbNow.example ?? "").trim() &&
                        !String(fbNow.improved ?? "").trim() && (
                          <div className="text-slate-400">這次回饋沒有可顯示的內容。</div>
                        )}

                      {draftView === "d1" && String(fbNow.improved ?? "").trim() && (
                        <button
                          type="button"
                          className="kid-btn-secondary w-full !text-xs"
                          onClick={() => applyImprovedToDraft2(focusStage)}
                        >
                          ✨ 一鍵套用到「草稿 2」
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
