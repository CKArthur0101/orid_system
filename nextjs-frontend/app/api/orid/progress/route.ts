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

export async function GET(req: Request) {
  const auth = await getBearerAuthorization(req);
  if (!auth) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const url = new URL(req.url);
  const qs = url.searchParams.toString();
  const target = `${API_BASE_URL}/orid/progress${qs ? `?${qs}` : ""}`;

  const r = await fetch(target, {
    method: "GET",
    headers: { Authorization: auth },
    cache: "no-store",
  });

  const text = await r.text();
  return jsonOrDetailResponse(r.status, text);
}
