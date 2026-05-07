import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://backend:8000";

async function getToken() {
  return (await cookies()).get("accessToken")?.value;
}

/** 後測列表 GET ?classId=&studentId=&week= */
export async function GET(req: NextRequest) {
  const token = await getToken();
  if (!token) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const classId = (req.nextUrl.searchParams.get("classId") ?? "").trim();
  const studentId = (req.nextUrl.searchParams.get("studentId") ?? "").trim();
  const week = req.nextUrl.searchParams.get("week") ?? "1";

  if (!classId || !studentId) {
    return NextResponse.json({ detail: "Missing classId or studentId" }, { status: 400 });
  }

  const r = await fetch(
    `${API_BASE_URL}/teacher/classes/${encodeURIComponent(classId)}/students/${encodeURIComponent(studentId)}/post-test?week=${encodeURIComponent(week)}`,
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

/** PUT ?classId=&studentId= ，body JSON 同後端 */
export async function PUT(req: NextRequest) {
  const token = await getToken();
  if (!token) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const classId = (req.nextUrl.searchParams.get("classId") ?? "").trim();
  const studentId = (req.nextUrl.searchParams.get("studentId") ?? "").trim();

  if (!classId || !studentId) {
    return NextResponse.json({ detail: "Missing classId or studentId" }, { status: 400 });
  }

  const body = await req.text();
  const r = await fetch(
    `${API_BASE_URL}/teacher/classes/${encodeURIComponent(classId)}/students/${encodeURIComponent(studentId)}/post-test`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
      },
      body,
    }
  );
  const text = await r.text();
  return new NextResponse(text, {
    status: r.status,
    headers: { "Content-Type": "application/json" },
  });
}
