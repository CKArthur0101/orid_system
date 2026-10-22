import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://backend:8000";

type Ctx = { params: Promise<{ classId: string }> };

export async function POST(_req: Request, ctx: Ctx) {
  const token = (await cookies()).get("accessToken")?.value;
  if (!token) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  const { classId } = await ctx.params;
  const r = await fetch(`${API_BASE_URL}/admin/classes/${classId}/archive`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
    cache: "no-store",
  });
  const text = await r.text();
  return new NextResponse(text, {
    status: r.status,
    headers: { "Content-Type": "application/json" },
  });
}
