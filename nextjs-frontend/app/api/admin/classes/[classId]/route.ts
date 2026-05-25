import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://backend:8000";

async function adminAuthHeaders(): Promise<{ Authorization: string } | NextResponse> {
  const token = (await cookies()).get("accessToken")?.value;
  if (!token) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  return { Authorization: `Bearer ${token}` };
}

async function proxyResponse(r: Response) {
  const text = await r.text();
  return new NextResponse(text, {
    status: r.status,
    headers: { "Content-Type": "application/json" },
  });
}

type Ctx = { params: Promise<{ classId: string }> };

export async function PATCH(req: Request, ctx: Ctx) {
  const auth = await adminAuthHeaders();
  if (auth instanceof NextResponse) return auth;
  const { classId } = await ctx.params;
  const body = await req.text();
  const r = await fetch(`${API_BASE_URL}/admin/classes/${classId}`, {
    method: "PATCH",
    headers: { Accept: "application/json", "Content-Type": "application/json", ...auth },
    body,
    cache: "no-store",
  });
  return proxyResponse(r);
}

export async function DELETE(_req: Request, ctx: Ctx) {
  const auth = await adminAuthHeaders();
  if (auth instanceof NextResponse) return auth;
  const { classId } = await ctx.params;
  const r = await fetch(`${API_BASE_URL}/admin/classes/${classId}`, {
    method: "DELETE",
    headers: { Accept: "application/json", ...auth },
    cache: "no-store",
  });
  if (r.status === 204) return new NextResponse(null, { status: 204 });
  return proxyResponse(r);
}
