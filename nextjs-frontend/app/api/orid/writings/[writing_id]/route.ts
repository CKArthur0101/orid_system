import { NextRequest, NextResponse } from "next/server";

import { parseAccessTokenFromCookieHeader } from "@/lib/orid-bff-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const API_BASE_URL =
  process.env.API_BASE_URL ||
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  "http://backend:8000";

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

export async function PUT(
  req: NextRequest,
  { params }: { params: Promise<{ writing_id: string }> }
) {
  try {
    const { writing_id: writingId } = await params;

    // 你前端通常送 { content: "..." }
    const bodyText = await req.text();

    const r = await fetch(`${API_BASE_URL}/orid/writings/${writingId}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        ...forwardHeaders(req),
      },
      body: bodyText,
      cache: "no-store",
    });

    const text = await r.text();
    return new NextResponse(text, {
      status: r.status,
      headers: {
        "Content-Type": r.headers.get("content-type") ?? "application/json",
      },
    });
  } catch (err: any) {
    return NextResponse.json(
      {
        detail: `route /api/orid/writings/[writing_id] PUT crashed: ${
          err?.message ?? String(err)
        }`,
      },
      { status: 500 }
    );
  }
}
