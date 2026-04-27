import { NextResponse } from "next/server";

import { getBearerAuthorization } from "@/lib/orid-bff-auth";

export async function POST(req: Request) {
  const auth = await getBearerAuthorization(req);
  if (!auth)
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });

  const { searchParams } = new URL(req.url);
  const week = searchParams.get("week");
  if (!week)
    return NextResponse.json({ detail: "Missing week" }, { status: 400 });

  const forceNew = searchParams.get("force_new");
  const condition = searchParams.get("condition");

  const base = process.env.API_BASE_URL ?? "http://backend:8000";

  const qs = new URLSearchParams({ week });
  if (forceNew) qs.set("force_new", forceNew);
  if (condition) qs.set("condition", condition);

  const r = await fetch(`${base}/orid/sessions/ensure?${qs.toString()}`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      Authorization: auth,
    },
    cache: "no-store",
  });

  const data = await r.json().catch(() => ({}));
  return NextResponse.json(data, { status: r.status });
}
