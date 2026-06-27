import { NextResponse } from "next/server";

import { getBearerAuthorization } from "@/lib/orid-bff-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://backend:8000";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function normalizeUuid(s: string) {
  return s.startsWith("urn:uuid:") ? s.slice("urn:uuid:".length) : s;
}

function passthrough(r: Response, text: string) {
  try {
    return NextResponse.json(JSON.parse(text), { status: r.status });
  } catch {
    const trimmed = (text || "").trim();
    const detail =
      trimmed && !trimmed.startsWith("<")
        ? trimmed.slice(0, 500)
        : r.ok
          ? "服務回應格式錯誤。"
          : "服務暫時無法處理請求，請稍後再試。";
    return NextResponse.json({ detail }, { status: r.ok ? 502 : r.status });
  }
}

export async function GET(req: Request) {
  const auth = await getBearerAuthorization(req);
  if (!auth) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const url = new URL(req.url);
  const qs = url.searchParams.toString();

  const r = await fetch(`${API_BASE_URL}/orid/writings${qs ? `?${qs}` : ""}`, {
    method: "GET",
    headers: { Authorization: auth },
    cache: "no-store",
  });

  const text = await r.text();
  return passthrough(r, text);
}

export async function POST(req: Request) {
  const auth = await getBearerAuthorization(req);
  if (!auth) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const body = await req.text();

  const r = await fetch(`${API_BASE_URL}/orid/writings`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: auth,
    },
    body,
    cache: "no-store",
  });

  const text = await r.text();
  return passthrough(r, text);
}

/**
 * 前端：PUT /api/orid/writings body:{ id, content }
 * 這裡做容錯：依序嘗試
 * 1) PUT /orid/writings/{id} body:{content}
 * 2) PUT /orid/writings body:{id, content}
 * 3) PATCH /orid/writings body:{id, content}
 */
export async function PUT(req: Request) {
  const auth = await getBearerAuthorization(req);
  if (!auth) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const json = await req.json().catch(() => ({} as any));
  const rawWritingId = String(json?.id ?? json?.writing_id ?? "").trim();
  const writingId = normalizeUuid(rawWritingId);
  const content: unknown = json?.content;

  if (!writingId) return NextResponse.json({ detail: "missing writing id" }, { status: 422 });
  if (!UUID_RE.test(writingId)) return NextResponse.json({ detail: "invalid writing id" }, { status: 422 });
  if (typeof content !== "string") return NextResponse.json({ detail: "missing content" }, { status: 422 });

  const headers = {
    "Content-Type": "application/json",
    Authorization: auth,
  };

  // 1) PUT /orid/writings/{id}
  let r = await fetch(`${API_BASE_URL}/orid/writings/${writingId}`, {
    method: "PUT",
    headers,
    body: JSON.stringify({ content }),
    cache: "no-store",
  });
  let text = await r.text();

  // 2) PUT /orid/writings
  if (r.status === 404 || r.status === 405) {
    r = await fetch(`${API_BASE_URL}/orid/writings`, {
      method: "PUT",
      headers,
      body: JSON.stringify({ id: writingId, content }),
      cache: "no-store",
    });
    text = await r.text();
  }

  // 3) PATCH /orid/writings
  if (r.status === 404 || r.status === 405) {
    r = await fetch(`${API_BASE_URL}/orid/writings`, {
      method: "PATCH",
      headers,
      body: JSON.stringify({ id: writingId, content }),
      cache: "no-store",
    });
    text = await r.text();
  }

  return passthrough(r, text);
}