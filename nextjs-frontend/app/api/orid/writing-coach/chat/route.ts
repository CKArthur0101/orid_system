import { NextResponse } from "next/server";

import { getBearerAuthorization } from "@/lib/orid-bff-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://backend:8000";

function jsonOrDetailResponse(status: number, text: string) {
  try {
    return NextResponse.json(JSON.parse(text), { status });
  } catch {
    return NextResponse.json(
      { detail: status >= 500 ? "服務暫時無法處理請求，請稍後再試。" : "請求失敗。" },
      { status },
    );
  }
}

export async function POST(req: Request) {
  const auth = await getBearerAuthorization(req);
  if (!auth) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const rawBody = await req.text();

  const r = await fetch(`${API_BASE_URL}/orid/writing-coach/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: auth,
    },
    body: rawBody,
    cache: "no-store",
  });

  const text = await r.text();
  return jsonOrDetailResponse(r.status, text);
}
