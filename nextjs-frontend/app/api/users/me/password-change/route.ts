import { NextResponse } from "next/server";

import { getBearerAuthorization } from "@/lib/orid-bff-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://backend:8000";

async function proxy(req: Request, method: "GET" | "POST") {
  const auth = await getBearerAuthorization(req);
  if (!auth) return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  const r = await fetch(`${API_BASE_URL}/users/password-change`, {
    method,
    headers: {
      Accept: "application/json",
      Authorization: auth,
      ...(method === "POST" ? { "Content-Type": "application/json" } : {}),
    },
    body: method === "POST" ? await req.text() : undefined,
    cache: "no-store",
  });
  const text = await r.text();
  return new NextResponse(text, {
    status: r.status,
    headers: { "Content-Type": "application/json" },
  });
}

export function GET(req: Request) {
  return proxy(req, "GET");
}

export function POST(req: Request) {
  return proxy(req, "POST");
}
