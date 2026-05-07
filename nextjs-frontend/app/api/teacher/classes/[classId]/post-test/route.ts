import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://backend:8000";

async function getToken() {
  return (await cookies()).get("accessToken")?.value;
}

/**
 * 別名：GET /classes/{id}/post-test?studentId=…&week=…
 * 與 /classes/{id}/students/{studentId}/post-test 同等。
 */
export async function GET(req: NextRequest, { params }: { params: Promise<{ classId: string }> }) {
  const token = await getToken();
  if (!token) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const { classId } = await params;
  const url = new URL(req.url);
  const studentId = url.searchParams.get("studentId");
  const week = url.searchParams.get("week") ?? "1";

  if (!studentId) {
    return NextResponse.json({ detail: "Missing studentId query parameter" }, { status: 400 });
  }

  const r = await fetch(
    `${API_BASE_URL}/teacher/classes/${classId}/students/${studentId}/post-test?week=${encodeURIComponent(week)}`,
    {
      headers: { Accept: "application/json", Authorization: `Bearer ${token}` },
      cache: "no-store",
    }
  );
  const text = await r.text();
  return new NextResponse(text, {
    status: r.status,
    headers: { "Content-Type": "application/json" },
  });
}

export async function PUT(req: NextRequest, { params }: { params: Promise<{ classId: string }> }) {
  const token = await getToken();
  if (!token) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const { classId } = await params;
  const url = new URL(req.url);
  const studentId = url.searchParams.get("studentId");
  if (!studentId) {
    return NextResponse.json({ detail: "Missing studentId query parameter" }, { status: 400 });
  }

  const body = await req.text();
  const r = await fetch(`${API_BASE_URL}/teacher/classes/${classId}/students/${studentId}/post-test`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
    body,
  });
  const text = await r.text();
  return new NextResponse(text, {
    status: r.status,
    headers: { "Content-Type": "application/json" },
  });
}
