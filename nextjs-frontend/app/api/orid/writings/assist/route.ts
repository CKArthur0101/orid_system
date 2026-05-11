import { NextRequest, NextResponse } from "next/server";

import { parseAccessTokenFromCookieHeader } from "@/lib/orid-bff-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const API_BASE_URL = process.env.API_BASE_URL || "http://backend:8000";

function forwardHeaders(req: NextRequest) {
  const cookie = req.headers.get("cookie") ?? "";
  const headerAuth = req.headers.get("authorization") ?? "";
  let token = req.cookies.get("accessToken")?.value ?? "";
  if (!token) token = parseAccessTokenFromCookieHeader(cookie) ?? "";
  const authorization = headerAuth || (token ? `Bearer ${token}` : "");

  return {
    ...(cookie ? { cookie } : {}),
    ...(authorization ? { Authorization: authorization } : {}),
  };
}

function passthrough(r: Response, text: string) {
  try {
    return NextResponse.json(JSON.parse(text), { status: r.status });
  } catch {
    return NextResponse.json(
      { detail: r.ok ? "服務回應格式錯誤。" : "服務暫時無法處理請求，請稍後再試。" },
      { status: r.ok ? 502 : r.status },
    );
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.text();

    const r = await fetch(`${API_BASE_URL}/orid/writings/assist`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...forwardHeaders(req),
      },
      body,
      cache: "no-store",
    });

    const text = await r.text();
    return passthrough(r, text);
  } catch (err: any) {
    return NextResponse.json({ detail: "服務暫時無法處理請求，請稍後再試。" }, { status: 500 });
  }
}
