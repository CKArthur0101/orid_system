import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://backend:8000";

export async function POST() {
  const cookieStore = await cookies();
  const token = cookieStore.get("accessToken")?.value;

  if (token) {
    try {
      await fetch(`${API_BASE_URL}/auth/jwt/logout`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        cache: "no-store",
      });
    } catch {
      // Local cookie cleanup is enough to complete logout for this app shell.
    }
  }

  cookieStore.delete("accessToken");
  return NextResponse.json({ ok: true });
}
