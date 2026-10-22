import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://backend:8000";

export async function POST(req: Request) {
  const token = (await cookies()).get("accessToken")?.value;
  if (!token) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  const form = await req.formData();
  const r = await fetch(`${API_BASE_URL}/admin/experiment/dry-run`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
    cache: "no-store",
  });
  const text = await r.text();
  return new NextResponse(text, {
    status: r.status,
    headers: { "Content-Type": "application/json" },
  });
}
