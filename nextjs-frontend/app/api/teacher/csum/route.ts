import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://backend:8000";

/** 教師 BFF：個人摘要。路徑故意極短，避開 Next 16 對 /teacher/class-* 的誤路由。 GET ?classId=&studentId=&week= */
export async function GET(req: NextRequest) {
  const token = (await cookies()).get("accessToken")?.value;
  if (!token) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const classId = (req.nextUrl.searchParams.get("classId") ?? "").trim();
  const studentId = (req.nextUrl.searchParams.get("studentId") ?? "").trim();
  const week = req.nextUrl.searchParams.get("week") ?? "1";

  if (!classId || !studentId) {
    return NextResponse.json({ detail: "Missing classId or studentId" }, { status: 400 });
  }

  const r = await fetch(
    `${API_BASE_URL}/teacher/classes/${encodeURIComponent(classId)}/students/${encodeURIComponent(studentId)}/summary?week=${encodeURIComponent(week)}`,
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
