import { NextResponse } from "next/server";

import { getBearerAuthorization } from "@/lib/orid-bff-auth";

export async function POST(req: Request) {
  const auth = await getBearerAuthorization(req);
  if (!auth) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const body = await req.json();
  const base = process.env.API_BASE_URL ?? "http://backend:8000";

  const r = await fetch(`${base}/orid/readings`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: auth,
    },
    body: JSON.stringify(body),
  });

  const data = await r.json().catch(() => ({}));
  return NextResponse.json(data, { status: r.status });
}
