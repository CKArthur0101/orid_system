import Link from "next/link";

import { login } from "@/components/actions/login-action";
import { DilabLogo } from "@/components/orid/DilabLogo";
import { LoginCornerDecorations } from "@/components/orid/LoginCornerDecorations";

const showRegisterLink =
  process.env.NEXT_PUBLIC_ENABLE_PUBLIC_REGISTRATION_AND_PASSWORD_RESET !== "false";

const INPUT_CLASS =
  "h-11 w-full rounded-xl border border-amber-200 bg-amber-50/50 px-3 text-base text-amber-950 placeholder:text-amber-400 outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-400/30";

function loginErrorMessage(error: string | undefined, detail: string | undefined): string | null {
  if (!error) return null;
  if (error === "validation") return "請確認帳號與密碼格式是否正確。";
  if (error === "auth") return detail?.trim() || "帳號或密碼不正確，請再試一次。";
  if (error === "server") return "系統暫時無法登入，請稍後再試。";
  return null;
}

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ error?: string; detail?: string }>;
}) {
  const sp = await searchParams;
  const errorMessage = loginErrorMessage(sp.error, sp.detail);

  return (
    <div className="orid-forest-page relative flex min-h-screen w-full items-center justify-center px-4 py-10 sm:py-12">
      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
        <div className="absolute -left-24 -top-24 h-72 w-72 rounded-full bg-amber-200/20 blur-3xl" />
        <div className="absolute -right-20 top-16 h-64 w-64 rounded-full bg-orange-200/15 blur-3xl" />
        <div className="absolute bottom-0 left-1/2 h-48 w-96 -translate-x-1/2 rounded-full bg-amber-300/10 blur-3xl" />
      </div>

      <LoginCornerDecorations />

      <div className="relative z-10 w-full max-w-md">
        <div className="mb-5 flex flex-col items-center gap-3 text-center">
          <div className="flex flex-col items-center gap-2.5 sm:flex-row sm:gap-3">
            <DilabLogo height={36} />
            <h1 className="text-2xl font-bold text-amber-950 sm:text-3xl">AI–ORID 反思寫作</h1>
          </div>
        </div>

        <form action={login} className="kid-shell p-5 sm:p-7">
          <h2 className="mb-1 text-center text-lg font-bold text-amber-950 sm:text-xl">
            歡迎回來！
          </h2>
          <p className="mb-5 text-center text-sm text-amber-800/60 sm:text-base">
            輸入你的帳號密碼登入系統
          </p>

          {errorMessage ? (
            <p className="mb-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {errorMessage}
            </p>
          ) : null}

          <div className="space-y-4">
            <div className="space-y-1.5">
              <label htmlFor="username" className="text-sm font-semibold text-amber-900 sm:text-base">
                帳號
              </label>
              <input
                id="username"
                name="username"
                type="text"
                autoComplete="username"
                required
                className={INPUT_CLASS}
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="password" className="text-sm font-semibold text-amber-900 sm:text-base">
                密碼
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                className={INPUT_CLASS}
              />
            </div>

            <div className="pt-1">
              <button type="submit" className="kid-btn-primary w-full">
                登入
              </button>
            </div>
          </div>
        </form>

        {showRegisterLink ? (
          <p className="mt-3 text-center text-sm text-amber-800/60 sm:text-base">
            還沒有帳號？{" "}
            <Link
              href="/register"
              className="font-semibold text-amber-700 underline-offset-2 hover:text-amber-900 hover:underline"
            >
              前往註冊
            </Link>
          </p>
        ) : null}
      </div>
    </div>
  );
}
