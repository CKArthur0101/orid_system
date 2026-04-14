import { cookies } from "next/headers";
import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://backend:8000";

function jsonOrDetailResponse(status: number, text: string) {
  try {
    return NextResponse.json(JSON.parse(text), { status });
  } catch {
    return NextResponse.json({ detail: text || `writing-coach chat failed (${status})` }, { status });
  }
}

export async function POST(req: Request) {
  const token = (await cookies()).get("accessToken")?.value;
  if (!token) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const rawBody = await req.text();

  const r = await fetch(`${API_BASE_URL}/orid/writing-coach/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: rawBody,
    cache: "no-store",
  });

  const text = await r.text();
  return jsonOrDetailResponse(r.status, text);
}
