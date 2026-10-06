"use client";

import { useEffect, useState } from "react";

type AppRole = "student" | "teacher" | "admin";

export type AuthenticatedUser = {
  email?: string | null;
  display_name?: string | null;
  role?: string | null;
};

type AuthState =
  | { status: "checking"; user: null }
  | { status: "ready"; user: AuthenticatedUser }
  | { status: "error"; user: null };

function destinationForRole(role: AppRole) {
  if (role === "admin") return "/admin/users";
  if (role === "teacher") return "/teacher";
  return "/home";
}

export function useAuthenticatedUser(requiredRole: AppRole): AuthState {
  const [state, setState] = useState<AuthState>({ status: "checking", user: null });

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const response = await fetch("/api/users/me", {
          credentials: "include",
          cache: "no-store",
        });
        if (cancelled) return;
        if (response.status === 401 || response.status === 403) {
          window.location.replace("/login?error=session");
          return;
        }
        if (!response.ok) {
          setState({ status: "error", user: null });
          return;
        }

        const user = (await response.json().catch(() => null)) as AuthenticatedUser | null;
        if (!user || cancelled) {
          setState({ status: "error", user: null });
          return;
        }

        const roleValue = String(user.role ?? "student").toLowerCase();
        const role: AppRole = roleValue === "admin" || roleValue === "teacher" ? roleValue : "student";
        if (role !== requiredRole) {
          window.location.replace(destinationForRole(role));
          return;
        }
        setState({ status: "ready", user });
      } catch {
        if (!cancelled) setState({ status: "error", user: null });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [requiredRole]);

  return state;
}
