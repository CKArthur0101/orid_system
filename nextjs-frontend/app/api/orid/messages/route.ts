import { NextResponse } from "next/server";

import { getBearerAuthorization } from "@/lib/orid-bff-auth";

export async function GET(req: Request) {
  const auth = await getBearerAuthorization(req);
  if (!auth) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const { searchParams } = new URL(req.url);
  const qs = searchParams.toString();
  const base = process.env.API_BASE_URL ?? "http://backend:8000";

  const r = await fetch(`${base}/orid/messages${qs ? `?${qs}` : ""}`, {
    method: "GET",
    headers: {
      Accept: "application/json",
      Authorization: auth,
    },
    cache: "no-store",
  });

  const text = await r.text();
  return new NextResponse(text, {
    status: r.status,
    headers: { "Content-Type": r.headers.get("content-type") ?? "application/json" },
  });
}
