"use server";

import { cookies } from "next/headers";

import { authJwtLogin } from "@/app/clientService";
import { redirect } from "next/navigation";
import { loginSchema } from "@/lib/definitions";
import { getErrorMessage } from "@/lib/utils";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://backend:8000";

const ACCESS_TOKEN_COOKIE_MAX_AGE_SEC = Number(
  process.env.ACCESS_TOKEN_COOKIE_MAX_AGE_SEC ?? 60 * 60 * 12,
);

/** Server-action login: works without client JavaScript (plain HTML form). */
export async function login(formData: FormData) {
  const validatedFields = loginSchema.safeParse({
    username: formData.get("username") as string,
    password: formData.get("password") as string,
  });

  if (!validatedFields.success) {
    redirect("/login?error=validation");
  }

  const { username, password } = validatedFields.data;

  let redirectTo = "/dashboard";

  try {
    const { data, error } = await authJwtLogin({
      body: { username, password },
    });
    if (error) {
      redirect(`/login?error=auth&detail=${encodeURIComponent(getErrorMessage(error))}`);
    }
    const secure = process.env.NODE_ENV === "production";
    (await cookies()).set("accessToken", data.access_token, {
      path: "/",
      sameSite: "lax",
      httpOnly: true,
      secure,
      maxAge: ACCESS_TOKEN_COOKIE_MAX_AGE_SEC,
    });
    try {
      const meRes = await fetch(`${API_BASE_URL}/users/me`, {
        headers: { Authorization: `Bearer ${data.access_token}` },
      });
      if (meRes.ok) {
        const me = await meRes.json();
        const role = String(me?.role ?? "student").toLowerCase();
        if (role === "admin") {
          redirectTo = "/admin/users";
        } else if (role === "teacher") {
          redirectTo = "/teacher";
        }
      }
    } catch {
      // role lookup failed — fall back to student dashboard
    }
  } catch (err) {
    if (err instanceof Error && err.message === "NEXT_REDIRECT") {
      throw err;
    }
    redirect("/login?error=server");
  }
  redirect(redirectTo);
}
