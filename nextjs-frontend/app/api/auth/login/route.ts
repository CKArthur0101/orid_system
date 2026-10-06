import { NextResponse } from "next/server";

import { loginSchema } from "@/lib/definitions";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://backend:8000";
const DEFAULT_COOKIE_MAX_AGE_SEC = 60 * 60 * 12;

function cookieMaxAgeSeconds(): number {
  const parsed = Number(process.env.ACCESS_TOKEN_COOKIE_MAX_AGE_SEC);
  return Number.isFinite(parsed) && parsed > 0
    ? Math.floor(parsed)
    : DEFAULT_COOKIE_MAX_AGE_SEC;
}

function loginRedirect(
  error: "validation" | "auth" | "server",
  detail?: string,
) {
  const params = new URLSearchParams({ error });
  if (detail) params.set("detail", detail);
  return new NextResponse(null, {
    status: 303,
    headers: { Location: `/login?${params.toString()}` },
  });
}

function backendErrorDetail(payload: unknown): string | undefined {
  if (!payload || typeof payload !== "object") return undefined;
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const reason = (detail as { reason?: unknown }).reason;
    if (typeof reason === "string") return reason;
  }
  return undefined;
}

export async function POST(request: Request) {
  let formData: FormData;
  try {
    formData = await request.formData();
  } catch {
    return loginRedirect("validation");
  }

  const parsed = loginSchema.safeParse({
    username: formData.get("username"),
    password: formData.get("password"),
  });
  if (!parsed.success) return loginRedirect("validation");

  const body = new URLSearchParams(parsed.data);

  try {
    const authResponse = await fetch(`${API_BASE_URL}/auth/jwt/login`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body,
      cache: "no-store",
    });

    const authPayload = await authResponse.json().catch(() => null);
    if (!authResponse.ok) {
      return loginRedirect(
        "auth",
        backendErrorDetail(authPayload) ?? "帳號或密碼不正確，請再試一次。",
      );
    }

    const accessToken = String(authPayload?.access_token ?? "").trim();
    if (!accessToken) return loginRedirect("server");

    const meResponse = await fetch(`${API_BASE_URL}/users/me`, {
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      cache: "no-store",
    });
    if (!meResponse.ok) return loginRedirect("server");

    const user = await meResponse.json().catch(() => null);
    if (!user || typeof user !== "object") return loginRedirect("server");

    const role = String(user.role ?? "student").toLowerCase();
    const destination = role === "admin" ? "/admin/users" : role === "teacher" ? "/teacher" : "/home";
    const response = new NextResponse(null, {
      status: 303,
      headers: { Location: destination },
    });
    response.headers.set("Cache-Control", "no-store");
    response.cookies.set("accessToken", accessToken, {
      path: "/",
      sameSite: "lax",
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      maxAge: cookieMaxAgeSeconds(),
    });
    return response;
  } catch {
    return loginRedirect("server");
  }
}
