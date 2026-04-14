"use client";

import { useState } from "react";

type ChatMsg = { role: "student" | "ai"; text: string };

export default function Page() {
  const [title, setTitle] = useState("測試文章");
  const [content, setContent] = useState("這是一篇用來測試 ORID 的短文...");
  const [readingId, setReadingId] = useState<string>("");
  const [sessionId, setSessionId] = useState<string>("");
  const [studentText, setStudentText] = useState("");
  const [stage, setStage] = useState<string>("-");
  const [stageTurn, setStageTurn] = useState<number>(0);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string>("");

  async function createReading() {
    setErr("");
    setLoading(true);
    try {
      const res = await fetch("/api/orid/readings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, content }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "createReading failed");
      setReadingId(data.id);
    } catch (e: any) {
      setErr(e.message || "error");
    } finally {
      setLoading(false);
    }
  }

  async function createSession() {
    setErr("");
    if (!readingId) return alert("請先建立 reading");
    setLoading(true);
    try {
      const res = await fetch("/api/orid/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reading_id: readingId, condition: "A" }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "createSession failed");

      setSessionId(data.id);
      setStage(data.current_stage ?? "O");
      setStageTurn(data.stage_turn ?? 0);
      setMessages([]);
    } catch (e: any) {
      setErr(e.message || "error");
    } finally {
      setLoading(false);
    }
  }

  async function sendChat() {
    setErr("");
    if (!sessionId) return alert("請先建立 session");
    const input = studentText.trim();
    if (!input) return;

    setStudentText("");
    setMessages((prev) => [...prev, { role: "student", text: input }]);

    setLoading(true);
    try {
      const res = await fetch("/api/orid/writing-coach/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          student_text: input,
          stage: "O",
          draft: "d1",
          source: "free_text",
          week: 1,
          save_feedback: false,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "chat failed");

      setStage(data.stage ?? "-");
      setStageTurn(0);
      setMessages((prev) => [...prev, { role: "ai", text: data.ai_reply }]);
    } catch (e: any) {
      setErr(e.message || "error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold">ORID Demo</h2>
        <div className="text-sm text-gray-600">
          reading → session → chat（先做出能看見後端的最小前端）
        </div>
        {err && <div className="text-sm text-red-600 mt-2">錯誤：{err}</div>}
      </div>

      <div className="rounded-lg bg-white p-4 shadow space-y-3">
        <div className="text-sm text-gray-600">Step 1：建立閱讀材料</div>
        <input
          className="w-full border rounded p-2"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <textarea
          className="w-full border rounded p-2"
          rows={4}
          value={content}
          onChange={(e) => setContent(e.target.value)}
        />
        <button className="border rounded px-3 py-2" onClick={createReading} disabled={loading}>
          建立 Reading
        </button>
        <div className="text-sm">
          reading_id：<span className="font-mono">{readingId || "-"}</span>
        </div>
      </div>

      <div className="rounded-lg bg-white p-4 shadow space-y-3">
        <div className="text-sm text-gray-600">Step 2：建立反思 Session</div>
        <button className="border rounded px-3 py-2" onClick={createSession} disabled={loading || !readingId}>
          建立 Session
        </button>
        <div className="text-sm">
          session_id：<span className="font-mono">{sessionId || "-"}</span>
        </div>
        <div className="text-sm">
          current_stage：<b>{stage}</b>　stage_turn：<b>{stageTurn}</b>
        </div>
      </div>

      <div className="rounded-lg bg-white p-4 shadow space-y-3">
        <div className="text-sm text-gray-600">Step 3：開始 ORID 對話</div>

        <div className="space-y-2">
          {messages.length === 0 && <div className="text-sm text-gray-500">尚無對話</div>}
          {messages.map((m, i) => (
            <div key={i} className="text-sm">
              <b>{m.role === "student" ? "你" : "AI"}：</b>{m.text}
            </div>
          ))}
        </div>

        <div className="flex gap-2">
          <input
            className="flex-1 border rounded p-2"
            value={studentText}
            onChange={(e) => setStudentText(e.target.value)}
            placeholder="輸入一句話..."
          />
          <button className="border rounded px-3 py-2" onClick={sendChat} disabled={loading || !sessionId}>
            送出
          </button>
        </div>
      </div>
    </div>
  );
}
