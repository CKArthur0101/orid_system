/** @jest-environment node */

import { POST } from "@/app/api/auth/login/route";

function loginRequest(username = "student01", password = "Password1!") {
  const body = new URLSearchParams({ username, password });
  return new Request("https://app.example.test/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
}

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("POST /api/auth/login", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    jest.restoreAllMocks();
  });

  it.each([
    ["student", "/home"],
    ["teacher", "/teacher"],
    ["admin", "/admin/users"],
  ])("sets a persistent cookie and redirects a %s", async (role, destination) => {
    global.fetch = jest
      .fn()
      .mockResolvedValueOnce(jsonResponse({ access_token: "valid-token", token_type: "bearer" }))
      .mockResolvedValueOnce(jsonResponse({ email: "person01", role }));

    const response = await POST(loginRequest());

    expect(response.status).toBe(303);
    expect(response.headers.get("location")).toBe(destination);
    const cookie = response.headers.get("set-cookie") ?? "";
    expect(cookie).toContain("accessToken=valid-token");
    expect(cookie).toContain("HttpOnly");
    expect(cookie).toContain("Path=/");
    expect(cookie).toContain("SameSite=lax");
    expect(cookie).toContain("Max-Age=43200");
  });

  it("does not set a cookie when credentials are rejected", async () => {
    global.fetch = jest
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "LOGIN_BAD_CREDENTIALS" }, 400));

    const response = await POST(loginRequest());

    expect(response.status).toBe(303);
    expect(response.headers.get("location")).toContain("/login?error=auth");
    expect(response.headers.get("set-cookie")).toBeNull();
  });

  it("does not set a cookie when the token cannot identify a user", async () => {
    global.fetch = jest
      .fn()
      .mockResolvedValueOnce(jsonResponse({ access_token: "bad-token", token_type: "bearer" }))
      .mockResolvedValueOnce(jsonResponse({ detail: "Unauthorized" }, 401));

    const response = await POST(loginRequest());

    expect(response.status).toBe(303);
    expect(response.headers.get("location")).toBe("/login?error=server");
    expect(response.headers.get("set-cookie")).toBeNull();
  });

  it("never exposes an internal deployment address in redirects", async () => {
    global.fetch = jest
      .fn()
      .mockResolvedValueOnce(jsonResponse({ access_token: "valid-token", token_type: "bearer" }))
      .mockResolvedValueOnce(jsonResponse({ email: "person01", role: "student" }));

    const body = new URLSearchParams({ username: "student01", password: "Password1!" });
    const response = await POST(
      new Request("http://0.0.0.0:3000/api/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          "X-Forwarded-Host": "app.dioridwriting.com",
          "X-Forwarded-Proto": "https",
        },
        body,
      }),
    );

    expect(response.headers.get("location")).toBe("/home");
    expect(response.headers.get("location")).not.toContain("0.0.0.0");
  });
});
