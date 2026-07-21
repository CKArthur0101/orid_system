import { NextResponse } from "next/server";

import { getBearerAuthorization } from "@/lib/orid-bff-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://backend:8000";
const FEEDBACK_FETCH_TIMEOUT_MS = 180_000;

export async function POST(req: Request) {
  const auth = await getBearerAuthorization(req);
  if (!auth) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const body = await req.text();

  try {
    const r = await fetch(`${API_BASE_URL}/orid/writings/feedback`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: auth,
      },
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(FEEDBACK_FETCH_TIMEOUT_MS),
    });

    const text = await r.text();
    if (!text.trim()) {
      return NextResponse.json(
        { detail: statusMessage(r.status) },
        { status: r.status || 502 },
      );
    }
    return new NextResponse(text, {
      status: r.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    console.error("POST /api/orid/writings/feedback proxy failed", err);
    return NextResponse.json(
      {
        detail:
          "連線暫時中斷，請再按一次「取得回饋」。若連續失敗，請稍等半分鐘後再試。",
      },
      { status: 503 },
    );
  }
}

function statusMessage(status: number): string {
  if (status >= 500) return "服務暫時無法處理請求，請稍後再試。";
  return "請求失敗。";
}
