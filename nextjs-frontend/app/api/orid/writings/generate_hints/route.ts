import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const API_BASE =
  process.env.ORID_API_BASE_URL ||
  process.env.API_BASE_URL ||
  process.env.BACKEND_API_BASE_URL;

export async function POST(req: NextRequest) {
  try {
    if (!API_BASE) {
      return NextResponse.json(
        { detail: "Missing API base URL. Please set ORID_API_BASE_URL (or API_BASE_URL / BACKEND_API_BASE_URL)." },
        { status: 500 }
      );
    }

    const body = await req.text();

    const token = (await cookies()).get("accessToken")?.value;
    if (!token) {
      return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
    }

    const upstream = await fetch(`${API_BASE}/orid/writings/generate_hints`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body,
      cache: "no-store",
    });

    const text = await upstream.text();

    return new NextResponse(text, {
      status: upstream.status,
      headers: {
        "Content-Type": upstream.headers.get("content-type") ?? "application/json; charset=utf-8",
      },
    });
  } catch (error: any) {
    return NextResponse.json(
      { detail: error?.message ?? "Proxy error: generate_hints failed" },
      { status: 500 }
    );
  }
}