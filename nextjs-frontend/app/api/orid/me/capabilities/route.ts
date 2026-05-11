import { NextResponse } from "next/server";

import { getBearerAuthorization } from "@/lib/orid-bff-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://backend:8000";

export async function GET(req: Request) {
  const auth = await getBearerAuthorization(req);
  if (!auth)
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const r = await fetch(`${API_BASE_URL}/orid/me/capabilities`, {
    headers: { Accept: "application/json", Authorization: auth },
    cache: "no-store",
  });
  const text = await r.text();
  try {
    return NextResponse.json(JSON.parse(text), { status: r.status });
  } catch {
    return NextResponse.json(
      { detail: r.ok ? "服務回應格式錯誤。" : "服務暫時無法處理請求，請稍後再試。" },
      { status: r.ok ? 502 : r.status },
    );
  }
}
