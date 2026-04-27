import { NextResponse } from "next/server";

import { getBearerAuthorization } from "@/lib/orid-bff-auth";

export async function GET(
  req: Request,
  ctx: { params: any } // ✅ Next 15 可能是 Promise
) {
  const auth = await getBearerAuthorization(req);
  if (!auth) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  // ✅ Next 15：params 可能是 Promise，先 await
  const p = await ctx.params;

  // ✅ 容錯：不管你的資料夾叫 [reading_id] / [readingId] / [id] 都能抓到
  const readingId: string | undefined =
    p?.reading_id ?? p?.readingId ?? p?.id ?? (p ? Object.values(p)[0] : undefined);

  if (!readingId) {
    return NextResponse.json({ detail: "Missing reading_id" }, { status: 400 });
  }

  const base = process.env.API_BASE_URL ?? "http://backend:8000";

  const r = await fetch(`${base}/orid/readings/${readingId}`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      Authorization: auth,
    },
    cache: "no-store",
  });

  const text = await r.text();
  return new NextResponse(text, {
    status: r.status,
    headers: { "Content-Type": "application/json" },
  });
}