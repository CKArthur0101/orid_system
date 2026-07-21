import { NextResponse } from "next/server";

import { getBearerAuthorization } from "@/lib/orid-bff-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://backend:8000";
/** Writing-coach chat can run two LLM calls; allow a long wait before giving up. */
const CHAT_FETCH_TIMEOUT_MS = 180_000;

function jsonOrDetailResponse(status: number, text: string) {
  try {
    return NextResponse.json(JSON.parse(text), { status });
  } catch {
    return NextResponse.json(
      {
        detail:
          status >= 500
            ? "服務暫時無法處理請求，請稍後再按一次「取得回饋」。"
            : "請求失敗。",
      },
      { status },
    );
  }
}

export async function POST(req: Request) {
  const auth = await getBearerAuthorization(req);
  if (!auth) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const rawBody = await req.text();

  try {
    const r = await fetch(`${API_BASE_URL}/orid/writing-coach/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: auth,
      },
      body: rawBody,
      cache: "no-store",
      signal: AbortSignal.timeout(CHAT_FETCH_TIMEOUT_MS),
    });

    const text = await r.text();
    return jsonOrDetailResponse(r.status, text);
  } catch (err) {
    console.error("POST /api/orid/writing-coach/chat proxy failed", err);
    return NextResponse.json(
      {
        detail: "連線暫時中斷，請再按一次「取得回饋」。若連續失敗，請稍等半分鐘後再試。",
      },
      { status: 503 },
    );
  }
}
