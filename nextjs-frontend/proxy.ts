import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://backend:8000";

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
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("from", "disabled_auth");
    return NextResponse.redirect(url, 307);
  }

  const token = request.cookies.get("accessToken")?.value;

  if (!token) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  try {
    const res = await fetch(`${API_BASE_URL}/users/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!res.ok) {
      const resp = NextResponse.redirect(new URL("/login", request.url));
      resp.cookies.delete("accessToken");
      return resp;
    }

    const user = await res.json();
    const role = String(user?.role ?? "student").toLowerCase();

    if (pathname.startsWith("/admin")) {
      if (role !== "admin") {
        return NextResponse.redirect(new URL("/dashboard", request.url));
      }
      return NextResponse.next();
    }

    if (pathname.startsWith("/teacher")) {
      if (role === "admin") {
        return NextResponse.redirect(new URL("/admin/users", request.url));
      }
      if (role !== "teacher") {
        return NextResponse.redirect(new URL("/dashboard", request.url));
      }
    }

    return NextResponse.next();
  } catch {
    return NextResponse.redirect(new URL("/login", request.url));
  }
}

export const config = {
  matcher: [
    "/register",
    "/password-recovery",
    "/password-recovery/:path*",
    "/dashboard/:path*",
    "/teacher/:path*",
    "/admin/:path*",
  ],
};
