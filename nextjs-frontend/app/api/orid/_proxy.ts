import { NextRequest } from "next/server";

function getBaseUrl() {
  // ✅ 你若前端跑在本機，通常用 http://localhost:8000
  // ✅ 若前端也在 docker，同網路可用 http://backend:8000
  return (process.env.ORID_BACKEND_URL || "http://localhost:8000").replace(/\/+$/, "");
}

export async function proxyToBackend(req: NextRequest, backendPath: string) {
  const base = getBaseUrl();
  const url = new URL(req.url);

  const target = new URL(base + backendPath);
  target.search = url.search; // 保留 query string

  const method = req.method.toUpperCase();
  const headers = new Headers();

  // 轉發必要 headers（cookie / auth）
  const cookie = req.headers.get("cookie");
  const auth = req.headers.get("authorization");
  const ct = req.headers.get("content-type");

  if (cookie) headers.set("cookie", cookie);
  if (auth) headers.set("authorization", auth);
  if (ct) headers.set("content-type", ct);
  headers.set("accept", "application/json");

  const bodyText = method === "GET" || method === "HEAD" ? undefined : await req.text();

  const resp = await fetch(target.toString(), {
    method,
    headers,
    body: bodyText && bodyText.length ? bodyText : undefined,
    cache: "no-store",
  });

  const out = await resp.text();
  return new Response(out, {
    status: resp.status,
    headers: {
      "content-type": resp.headers.get("content-type") || "application/json",
    },
  });
}
