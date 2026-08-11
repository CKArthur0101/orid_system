export async function logoutToLogin() {
  try {
    await fetch("/api/auth/logout", {
      method: "POST",
      credentials: "include",
      cache: "no-store",
    });
  } finally {
    window.location.assign("/login");
  }
}
