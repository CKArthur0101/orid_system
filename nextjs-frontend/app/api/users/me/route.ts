import { NextResponse } from "next/server";

import { getBearerAuthorization } from "@/lib/orid-bff-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://backend:8000";

function parseForceNewAllowlist(): Set<string> {
  const raw = process.env.ORID_FORCE_NEW_ALLOWLIST ?? "";
  return new Set(
    raw
      .split(",")
      .map((x) => x.trim().toLowerCase())
      .filter(Boolean),
  );
}

export async function GET(req: Request) {
  const auth = await getBearerAuthorization(req);
  if (!auth) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const r = await fetch(`${API_BASE_URL}/users/me`, {
    headers: { Accept: "application/json", Authorization: auth },
    cache: "no-store",
  });
  const text = await r.text();
  if (!r.ok) {
    try {
      return NextResponse.json(JSON.parse(text), { status: r.status });
    } catch {
      return NextResponse.json({ detail: "服務暫時無法處理請求，請稍後再試。" }, { status: r.status });
    }
  }
  let user: Record<string, unknown> = {};
  try {
    user = text ? JSON.parse(text) : {};
  } catch {
    return NextResponse.json({ detail: "服務回應格式錯誤。" }, { status: 502 });
  }
  const allow = parseForceNewAllowlist();
  const email = String(user?.email ?? "")
    .trim()
    .toLowerCase();
  const orid_can_force_new = allow.size > 0 && !!email && allow.has(email);

  return NextResponse.json({ ...user, orid_can_force_new });
}
