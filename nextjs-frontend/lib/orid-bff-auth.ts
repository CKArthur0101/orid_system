import { cookies } from "next/headers";

/**
 * Parse accessToken from a raw Cookie header (fallback when cookies() is empty in Route Handlers).
 */
export function parseAccessTokenFromCookieHeader(
  cookieHeader: string | null
): string | undefined {
  if (!cookieHeader) return undefined;
  const m = cookieHeader.match(/(?:^|;\s*)accessToken=([^;]+)/);
  if (!m) return undefined;
  try {
    return decodeURIComponent(m[1].trim());
  } catch {
    return m[1].trim();
  }
}

/**
 * Bearer token for BFF → FastAPI. Order: Authorization header, cookies() store, Cookie header parse.
 */
export async function getBearerAuthorization(req: Request): Promise<string> {
  const headerAuth = (req.headers.get("authorization") ?? "").trim();
  if (headerAuth.toLowerCase().startsWith("bearer ") && headerAuth.length > 7) {
    return headerAuth;
  }

  const fromStore = (await cookies()).get("accessToken")?.value?.trim();
  if (fromStore) return `Bearer ${fromStore}`;

  const parsed = parseAccessTokenFromCookieHeader(
    req.headers.get("cookie")
  )?.trim();
  if (parsed) return `Bearer ${parsed}`;

  return "";
}
