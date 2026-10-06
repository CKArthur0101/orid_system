import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://backend:8000";

function firstForwardedValue(value: string | null) {
  return value?.split(",", 1)[0]?.trim() || null;
}

function publicUrl(request: NextRequest, path: string) {
  const forwardedHost = firstForwardedValue(request.headers.get("x-forwarded-host"));
  const host = forwardedHost ?? request.headers.get("host");
  const forwardedProto = firstForwardedValue(request.headers.get("x-forwarded-proto"));
  const protocol = forwardedProto ?? request.nextUrl.protocol.replace(":", "");

  if (host) return new URL(path, `${protocol}://${host}`);

  const fallback = request.nextUrl.clone();
  const target = new URL(path, fallback);
  fallback.pathname = target.pathname;
  fallback.search = target.search;
  return fallback;
}

function redirect(request: NextRequest, path: string, status = 307) {
  return NextResponse.redirect(publicUrl(request, path), status);
}

/** 與後端 ENABLE_PUBLIC_REGISTRATION_AND_PASSWORD_RESET 一併收斂；僅在明確設 false 時封鎖註冊／忘記密碼頁 */
function isDisabledAuthPath(pathname: string) {
  if (process.env.NEXT_PUBLIC_ENABLE_PUBLIC_REGISTRATION_AND_PASSWORD_RESET !== "false") {
    return false;
  }
  return (
    pathname === "/register" ||
    pathname === "/password-recovery" ||
    pathname.startsWith("/password-recovery/")
  );
}

export async function proxy(request: NextRequest) {
  const pathname = request.nextUrl.pathname;
  if (isDisabledAuthPath(pathname)) {
    return redirect(request, "/login?from=disabled_auth");
  }

  const token = request.cookies.get("accessToken")?.value;

  if (!token) {
    return redirect(request, "/login");
  }

  try {
    const res = await fetch(`${API_BASE_URL}/users/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!res.ok) {
      const resp = redirect(request, "/login");
      resp.cookies.delete("accessToken");
      return resp;
    }

    const user = await res.json();
    const role = String(user?.role ?? "student").toLowerCase();

    if (pathname.startsWith("/admin")) {
      if (role !== "admin") {
        return redirect(request, "/home");
      }
      return NextResponse.next();
    }

    if (pathname.startsWith("/teacher")) {
      if (role === "admin") {
        return redirect(request, "/admin/users");
      }
      if (role !== "teacher") {
        return redirect(request, "/home");
      }
    }

    return NextResponse.next();
  } catch {
    return redirect(request, "/login");
  }
}

export const config = {
  matcher: [
    "/register",
    "/password-recovery",
    "/password-recovery/:path*",
    "/home",
    "/home/:path*",
    "/week/:path*",
    "/dashboard/:path*",
    "/teacher/:path*",
    "/admin/:path*",
  ],
};
