import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://backend:8000";

/**
 * 別名：有些人／舊連結會打成 /classes/{id}/summary?studentId=…
 * （與 student-summary 相同行為，避免 Next 回 404）。
 */
export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ classId: string }> }
) {
  const token = (await cookies()).get("accessToken")?.value;
  if (!token) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const { classId } = await params;
  const url = new URL(req.url);
  const studentId = url.searchParams.get("studentId");
  const week = url.searchParams.get("week") ?? "1";

  if (!studentId) {
    return NextResponse.json({ detail: "Missing studentId query parameter" }, { status: 400 });
  }

  const r = await fetch(
    `${API_BASE_URL}/teacher/classes/${classId}/students/${studentId}/summary?week=${encodeURIComponent(week)}`,
    {
      method: "GET",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
      },
      cache: "no-store",
    }
  );

  const text = await r.text();
  return new NextResponse(text, {
    status: r.status,
    headers: { "Content-Type": "application/json" },
  });
}
