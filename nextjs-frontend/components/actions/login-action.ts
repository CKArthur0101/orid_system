"use server";

import { cookies } from "next/headers";

import { authJwtLogin } from "@/app/clientService";
import { redirect } from "next/navigation";
import { loginSchema } from "@/lib/definitions";
import { getErrorMessage } from "@/lib/utils";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://backend:8000";

/** Long-lived login: keep until manual logout (practically long max-age). */
const ACCESS_TOKEN_COOKIE_MAX_AGE_SEC = 60 * 60 * 24 * 365;

export async function login(prevState: unknown, formData: FormData) {
  const validatedFields = loginSchema.safeParse({
    username: formData.get("username") as string,
    password: formData.get("password") as string,
  });

  if (!validatedFields.success) {
    return {
      errors: validatedFields.error.flatten().fieldErrors,
    };
  }

  const { username, password } = validatedFields.data;

  const input = {
    body: {
      username,
      password,
    },
  };

  let redirectTo = "/dashboard";

  try {
    const { data, error } = await authJwtLogin(input);
    if (error) {
      return { server_validation_error: getErrorMessage(error) };
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
        if (role === "teacher" || role === "admin") {
          redirectTo = "/teacher";
        }
      }
    } catch {
      // role lookup failed — fall back to student dashboard
    }
  } catch (err) {
    console.error("Login error:", err);
    return {
      server_error: "An unexpected error occurred. Please try again later.",
    };
  }
  redirect(redirectTo);
}
