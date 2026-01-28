import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const API_BASE_URL = process.env.API_BASE_URL || "http://backend:8000";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function normalizeUuid(s: string) {
  return s.startsWith("urn:uuid:") ? s.slice("urn:uuid:".length) : s;
}

// ✅ 共用：cookie + (從 cookie 補) Authorization 一起轉發
function forwardHeaders(req: NextRequest) {
  const cookie = req.headers.get("cookie") ?? "";
  const headerAuth = req.headers.get("authorization") ?? "";

  // 從 cookie 讀 accessToken
  const token = req.cookies.get("accessToken")?.value ?? "";
  const authorization = headerAuth || (token ? `Bearer ${token}` : "");

  return {
    ...(cookie ? { cookie } : {}),
    ...(authorization ? { Authorization: authorization } : {}),
  };
}

function passthrough(r: Response, text: string) {
  return new NextResponse(text, {
    status: r.status,
    headers: {
      "Content-Type": r.headers.get("content-type") ?? "application/json",
    },
  });
}

export async function GET(req: NextRequest) {
  try {
    const url = new URL(req.url);
    const qs = url.searchParams.toString();

    const r = await fetch(`${API_BASE_URL}/orid/writings${qs ? `?${qs}` : ""}`, {
      method: "GET",
      headers: {
        ...forwardHeaders(req),
      },
      cache: "no-store",
    });

    const text = await r.text();
    return passthrough(r, text);
  } catch (err: any) {
    return NextResponse.json(
      { detail: `route /api/orid/writings GET crashed: ${err?.message ?? String(err)}` },
      { status: 500 }
    );
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.text();

    const r = await fetch(`${API_BASE_URL}/orid/writings`, {
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
    return NextResponse.json(
      { detail: `route /api/orid/writings POST crashed: ${err?.message ?? String(err)}` },
      { status: 500 }
    );
  }
}

/**
 * ✅ PUT 更新（做「容錯」）
 * 你的後端可能是以下其中一種：
 * A) PUT /orid/writings/{id}   body: { content }
 * B) PUT /orid/writings       body: { id, content }
 * C) PATCH /orid/writings     body: { id, content }   (少見但有人這樣做)
 *
 * 你前端固定呼叫：PUT /api/orid/writings body:{ id, content }
 * 這裡會自動去試到成功為止。
 */
export async function PUT(req: NextRequest) {
  try {
	  const json = await req.json().catch(() => ({}));
	  const rawWritingId: string = String(json?.id ?? json?.writing_id ?? "").trim();
	  const writingId = normalizeUuid(rawWritingId);
    const content: unknown = json?.content;

	  if (!writingId) {
      return NextResponse.json({ detail: "missing writing id" }, { status: 422 });
    }
	  if (!UUID_RE.test(writingId)) {
	    return NextResponse.json(
	      { detail: `invalid writing id: ${rawWritingId}` },
	      { status: 422 }
	    );
	  }
    if (typeof content !== "string") {
      return NextResponse.json({ detail: "missing content" }, { status: 422 });
    }

    const headers = {
      "Content-Type": "application/json",
      ...forwardHeaders(req),
    };

    // 1) 先試：PUT /orid/writings/{id}
    let r = await fetch(`${API_BASE_URL}/orid/writings/${writingId}`, {
      method: "PUT",
      headers,
      body: JSON.stringify({ content }),
      cache: "no-store",
    });
    let text = await r.text();

    // 如果 404/405，代表後端不是走這條路
    if (r.status === 404 || r.status === 405) {
      // 2) 再試：PUT /orid/writings  body:{id, content}
      r = await fetch(`${API_BASE_URL}/orid/writings`, {
        method: "PUT",
        headers,
        body: JSON.stringify({ id: writingId, content }),
        cache: "no-store",
      });
      text = await r.text();
    }

    // 如果還是 404/405，再試 PATCH（有些人用 PATCH）
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
  } catch (err: any) {
    return NextResponse.json(
      { detail: `route /api/orid/writings PUT crashed: ${err?.message ?? String(err)}` },
      { status: 500 }
    );
  }
}
