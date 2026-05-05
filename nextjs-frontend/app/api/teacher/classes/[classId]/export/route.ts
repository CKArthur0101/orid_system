import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://backend:8000";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ classId: string }> }
) {
  const token = (await cookies()).get("accessToken")?.value;
  if (!token) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const { classId } = await params;
  const week = new URL(req.url).searchParams.get("week") ?? "1";

  const r = await fetch(
    `${API_BASE_URL}/teacher/classes/${classId}/export?week=${encodeURIComponent(week)}`,
    {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    }
  );

  if (!r.ok) {
    return NextResponse.json({ detail: "Export failed" }, { status: r.status });
  }

  const blob = await r.blob();
  const cd = r.headers.get("Content-Disposition") ?? `attachment; filename="export_week${week}.csv"`;
  return new NextResponse(blob, {
    status: 200,
    headers: {
      "Content-Type": "text/csv; charset=utf-8-sig",
      "Content-Disposition": cd,
    },
  });
}
