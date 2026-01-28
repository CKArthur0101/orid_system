"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import WritingPanel, {
  OridWritingV1,
  StageKey,
  ConditionKey,
} from "@/components/orid/WritingPanel";

type ChatMsg = { role: "student" | "ai"; text: string };

// --- utils ---
const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function isUuid(v?: string | null): v is string {
  return !!v && UUID_RE.test(v);
}

const STAGES = [
  { key: "O", label: "O (Objective)" },
  { key: "R", label: "R (Reflective)" },
  { key: "I", label: "I (Interpretive)" },
  { key: "D", label: "D (Decisional)" },
] as const;

function stageLabel(s?: string) {
  const hit = STAGES.find((x) => x.key === s);
  return hit ? hit.label : "O (Objective)";
}

export default function WeekBookPage() {
  const params = useParams();
  const raw = (params as any)?.week;
  const weekStr = Array.isArray(raw) ? raw[0] : raw;
  const weekNum = Number(weekStr);

  if (!weekStr || Number.isNaN(weekNum)) {
    return <div className="p-6">週次格式不正確</div>;
  }

  if (weekNum !== 1) {
    return (
      <div className="p-6 space-y-4">
        <h1 className="text-2xl font-semibold">第 {weekNum} 週尚未開放</h1>
        <p className="text-sm text-muted-foreground">
          目前只開放第 1 週測試。之後會依研究進度解鎖。
        </p>
        <Link
          href="/dashboard/books"
          className="inline-flex items-center justify-center rounded-md border px-4 py-2 hover:bg-muted"
        >
          回書籍列表
        </Link>
      </div>
    );
  }

  // --- state: create reading/session ---
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [readingId, setReadingId] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);

  // --- state: chat ---
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [currentStage, setCurrentStage] = useState<string>("O");

  // --- state: writing (NEW) ---
  const [condition, setCondition] = useState<ConditionKey>("genai");
  const [activeWriteStage, setActiveWriteStage] = useState<StageKey>("O");

  const emptyWriting: OridWritingV1 = useMemo(
    () => ({
      schema: "orid_writing_v1",
      week: weekNum,
      stages: {
        O: { d1: "", d2: "" },
        R: { d1: "", d2: "" },
        I: { d1: "", d2: "" },
        D: { d1: "", d2: "" },
      },
    }),
    [weekNum]
  );

  const [writingData, setWritingData] = useState<OridWritingV1>(emptyWriting);
  const [writingSubmitting, setWritingSubmitting] = useState(false);
  const [writingId, setWritingId] = useState<string | null>(null);
  const [writingError, setWritingError] = useState<string | null>(null);
  const [writingLoadedOnce, setWritingLoadedOnce] = useState(false);

  const canChat = useMemo(() => !!sessionId && !loading, [sessionId, loading]);

  const hasAnyText = useMemo(() => {
    return Object.values(writingData.stages).some(
      (s) => (s.d1?.trim() || s.d2?.trim())?.length > 0
    );
  }, [writingData]);

  // ✅ 自動捲到底
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  // ✅ session 建立後：自動載入本週最新 writing
  useEffect(() => {
    if (!sessionId) return;

    const ac = new AbortController();

    (async () => {
      try {
        const qs = new URLSearchParams({
          latest: "true",
          session_id: sessionId,
          week: String(weekNum),
        });

        const res = await fetch(`/api/orid/writings?${qs.toString()}`, {
          method: "GET",
          cache: "no-store",
          signal: ac.signal,
        });

        if (!res.ok) return;

        const data = await res.json();
        const w = Array.isArray(data) ? data[0] : data;

        if (w?.content) {
          const rawContent = String(w.content);
          try {
            const parsed = JSON.parse(rawContent);
            if (parsed?.schema === "orid_writing_v1" && parsed?.stages) {
              // 讓 week 一致
              setWritingData({ ...parsed, week: weekNum });
            } else {
              // 舊資料或非預期：放到 O.d1
              setWritingData({
                ...emptyWriting,
                stages: {
                  ...emptyWriting.stages,
                  O: { ...emptyWriting.stages.O, d1: rawContent },
                },
              });
            }
          } catch {
            setWritingData({
              ...emptyWriting,
              stages: {
                ...emptyWriting.stages,
                O: { ...emptyWriting.stages.O, d1: rawContent },
              },
            });
          }

          setWritingLoadedOnce(true);
        } else {
          setWritingLoadedOnce(false);
          setWritingData(emptyWriting);
        }

        if (isUuid(String(w?.id))) setWritingId(String(w.id));
      } catch {
        // ignore
      }
    })();

    return () => ac.abort();
  }, [sessionId, weekNum, emptyWriting]);

  async function startWeek1() {
    try {
      setLoading(true);
      setError(null);

      // reset chat
      setMessages([]);
      setChatError(null);
      setInput("");
      setCurrentStage("O");

      // reset writing
      setWritingData(emptyWriting);
      setActiveWriteStage("O");
      setWritingId(null);
      setWritingError(null);
      setWritingLoadedOnce(false);

      // 1) reading
      const r1 = await fetch("/api/orid/readings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: "第 1 週（暫定教材）",
          content: "先用測試文字，之後再換正式教材。",
        }),
      });

      if (!r1.ok) {
        const text = await r1.text();
        throw new Error(`建立 reading 失敗：${r1.status} ${text}`);
      }

      const reading = await r1.json();
      setReadingId(reading.id);

      // 2) session
      const r2 = await fetch("/api/orid/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reading_id: reading.id,
          condition, // ✅ 用頁面上選的組別（genai/template）
        }),
      });

      if (!r2.ok) {
        const text = await r2.text();
        throw new Error(`建立 session 失敗：${r2.status} ${text}`);
      }

      const session = await r2.json();
      setSessionId(session.id);

      // initial AI msg
      setMessages([
        {
          role: "ai",
          text: "我們開始第 1 週的 ORID 對話囉！先用 1–2 句話客觀說說故事發生了什麼？（不要加入感想）",
        },
      ]);
    } catch (e: any) {
      setError(e?.message ?? "發生未知錯誤");
    } finally {
      setLoading(false);
    }
  }

  async function sendChat() {
    if (!sessionId) return;
    const text = input.trim();
    if (!text) return;

    try {
      setChatLoading(true);
      setChatError(null);

      setMessages((prev) => [...prev, { role: "student", text }]);
      setInput("");

      const r = await fetch("/api/orid/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          student_text: text,
        }),
      });

      if (!r.ok) {
        const respText = await r.text();
        throw new Error(`聊天失敗：${r.status} ${respText}`);
      }

      const data = await r.json();
      setMessages((prev) => [...prev, { role: "ai", text: data.ai_reply }]);

      if (data?.current_stage) setCurrentStage(String(data.current_stage));
    } catch (e: any) {
      setChatError(e?.message ?? "聊天發生未知錯誤");
    } finally {
      setChatLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      if (!chatLoading) sendChat();
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">本週教材：第 {weekNum} 週</h1>
        <p className="text-sm text-muted-foreground">
          整合：閱讀內容 + ORID 對話 + ORID 分段寫作（四段×雙稿）+ 可重整續接
        </p>
      </div>

      {/* 閱讀 */}
      <Card>
        <CardHeader>
          <CardTitle>📖 閱讀內容（暫時）</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          目前先用測試文字；等你選好正式教材後，我們再把 reading 內容接進來。
        </CardContent>
      </Card>

      {/* 開始本週活動：不要撐高 */}
      <Card>
        <CardHeader>
          <CardTitle>✅ 開始本週活動</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-3 items-center">
            <button
              onClick={startWeek1}
              disabled={loading}
              className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-primary-foreground hover:opacity-90 disabled:opacity-50"
            >
              {loading ? "建立中..." : "開始第 1 週活動（建立 session）"}
            </button>

            <select
              className="rounded-md border px-3 py-2 text-sm"
              value={condition}
              onChange={(e) => setCondition(e.target.value as ConditionKey)}
              title="用來展示兩組差異（之後可由班級分組自動帶入）"
            >
              <option value="genai">實驗組：GenAI 回饋</option>
              <option value="template">對照組：規則模板回饋</option>
            </select>

            <Link
              href="/dashboard/books"
              className="inline-flex items-center justify-center rounded-md border px-4 py-2 hover:bg-muted"
            >
              回書籍列表
            </Link>
          </div>

          <div className="text-sm text-muted-foreground">
            {error && <div className="text-red-600">{error}</div>}
            {readingId && <div>reading_id: {readingId}</div>}
            {sessionId && <div>session_id: {sessionId}</div>}
          </div>
        </CardContent>
      </Card>

      {/* ✅ 左右兩欄：左=大聊天室、右=寫作 */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* 左：聊天室 */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between gap-3">
              <CardTitle>💬 ORID 對話</CardTitle>
              <span className="text-xs text-muted-foreground">
                目前階段：{" "}
                <span className="font-medium">{stageLabel(currentStage)}</span>
              </span>
            </div>

            <div className="mt-3 flex flex-wrap gap-2">
              {STAGES.map((s) => {
                const active = currentStage === s.key;
                return (
                  <span
                    key={s.key}
                    className={[
                      "inline-flex items-center rounded-full border px-3 py-1 text-xs",
                      active
                        ? "bg-primary text-primary-foreground border-primary"
                        : "bg-muted/30",
                    ].join(" ")}
                  >
                    {s.label}
                  </span>
                );
              })}
            </div>
          </CardHeader>

          <CardContent>
            <div className="rounded-xl border bg-background">
              {/* 大視窗 */}
              <div className="h-[520px] overflow-auto p-4 space-y-3">
                {messages.length === 0 ? (
                  <div className="text-sm text-muted-foreground">
                    先按上面的「開始第 1 週活動」建立 session，才可以開始聊天。
                  </div>
                ) : (
                  messages.map((m, idx) => {
                    const isStudent = m.role === "student";
                    return (
                      <div
                        key={idx}
                        className={[
                          "flex items-end gap-3",
                          isStudent ? "justify-end" : "justify-start",
                        ].join(" ")}
                      >
                        {!isStudent && (
                          <div className="h-8 w-8 shrink-0 rounded-full border bg-muted flex items-center justify-center text-xs">
                            🤖
                          </div>
                        )}

                        <div
                          className={[
                            "max-w-[78%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm",
                            isStudent
                              ? "bg-emerald-100 text-foreground"
                              : "bg-sky-100 text-foreground",
                          ].join(" ")}
                        >
                          <div className="font-semibold mb-1">
                            {isStudent ? "學生：" : "AI："}
                          </div>
                          <div className="whitespace-pre-wrap">{m.text}</div>
                        </div>

                        {isStudent && (
                          <div className="h-8 w-8 shrink-0 rounded-full border bg-muted flex items-center justify-center text-xs">
                            🧑
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
                <div ref={chatEndRef} />
              </div>

              {/* 輸入列 */}
              <div className="border-t p-3">
                <div className="flex items-center gap-2">
                  <div className="flex-1 flex items-center gap-2 rounded-full border px-4 py-2">
                    <input
                      className="flex-1 bg-transparent text-sm outline-none"
                      placeholder={canChat ? "請輸入你的回應…" : "請先建立 session"}
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      onKeyDown={handleKeyDown}
                      disabled={!canChat || chatLoading}
                    />
                    <button
                      type="button"
                      title="語音（暫未啟用）"
                      className="rounded-full px-2 py-1 text-muted-foreground hover:bg-muted"
                      onClick={() => {}}
                    >
                      🎤
                    </button>
                  </div>

                  <button
                    onClick={sendChat}
                    disabled={!canChat || chatLoading || !input.trim()}
                    className="inline-flex items-center justify-center rounded-full bg-primary px-5 py-2 text-sm text-primary-foreground hover:opacity-90 disabled:opacity-50"
                  >
                    {chatLoading ? "送出中..." : "送出 ➤"}
                  </button>
                </div>

                {chatError && (
                  <div className="mt-2 text-sm text-red-600">{chatError}</div>
                )}
                <div className="mt-2 text-xs text-muted-foreground">
                  提示：國小生可能亂回；下一步會加「回答檢核」，不合格不跳階段。
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 右：寫作 */}
        <Card>
          <CardHeader>
            <CardTitle>✍️ 反思寫作（ORID 四段 × 雙稿）</CardTitle>
          </CardHeader>

          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              建立 session 後會自動載入本週最新草稿；送出/更新會寫入
              orid_writings（content 以 JSON 儲存，可續寫）。
            </p>

            {writingLoadedOnce && isUuid(writingId) && (
              <div className="text-sm text-muted-foreground">
                📝 已載入本週最新草稿（writing_id:{" "}
                <span className="font-mono">{writingId}</span>）
              </div>
            )}

            <WritingPanel
              data={writingData}
              setData={setWritingData}
              activeStage={activeWriteStage}
              setActiveStage={setActiveWriteStage}
              currentStageFromChat={currentStage}
              condition={condition}
            />

            <div className="flex gap-2">
              <button
                type="button"
                className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-primary-foreground hover:opacity-90 disabled:opacity-50"
                disabled={
                  !sessionId || !readingId || writingSubmitting || !hasAnyText
                }
                onClick={async () => {
                  if (!sessionId || !readingId) return;

                  try {
                    setWritingSubmitting(true);
                    setWritingError(null);

                    const content = JSON.stringify(writingData);

                    // ✅ 統一走 /api/orid/writings
                    // - 新增：POST body: { reading_id, session_id, week, content }
                    // - 更新：PUT  body: { id, content }
                    const isUpdate = isUuid(writingId);
                    const url = `/api/orid/writings`;
                    const method = isUpdate ? "PUT" : "POST";

                    const body = isUpdate
                      ? { id: writingId, content }
                      : {
                          reading_id: readingId,
                          session_id: sessionId,
                          week: weekNum,
                          content,
                        };

                    const r = await fetch(url, {
                      method,
                      credentials: "include",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify(body),
                    });

                    const text = await r.text();
                    if (!r.ok) {
                      setWritingError(text || `寫作送出失敗（${r.status}）`);
                      return;
                    }

                    const data = text ? JSON.parse(text) : null;
                    if (isUuid(data?.id)) setWritingId(String(data.id));
                    setWritingLoadedOnce(true);
                  } catch (err: any) {
                    setWritingError(err?.message ?? "寫作送出失敗");
                  } finally {
                    setWritingSubmitting(false);
                  }
                }}
              >
                {writingSubmitting
                  ? "送出中…"
                  : isUuid(writingId)
                    ? "更新反思"
                    : "送出反思"}
              </button>

              <button
                type="button"
                className="inline-flex items-center justify-center rounded-md border px-4 py-2 hover:bg-muted"
                onClick={() => {
                  setWritingData(emptyWriting);
                  setActiveWriteStage("O");
                  setWritingId(null);
                  setWritingError(null);
                  setWritingLoadedOnce(false);
                }}
              >
                清空
              </button>
            </div>

            {isUuid(writingId) && (
              <div className="text-sm text-muted-foreground">
                ✅ 已儲存成功！writing_id:{" "}
                <span className="font-mono">{writingId}</span>
              </div>
            )}

            {writingError && (
              <div className="text-sm text-red-600 whitespace-pre-wrap">
                ❌ {writingError}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <div>
        <Link
          href="/dashboard/orid-demo"
          className="text-sm underline text-muted-foreground hover:text-foreground"
        >
          （暫時）前往 ORID 測試頁
        </Link>
      </div>
    </div>
  );
}
