"use client";

import Link from "next/link";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { login } from "@/components/actions/login-action";
import { useActionState } from "react";
import { SubmitButton } from "@/components/ui/submitButton";
import { FieldError, FormError } from "@/components/ui/FormError";
import { DilabLogo } from "@/components/orid/DilabLogo";
import { LoginCornerDecorations } from "@/components/orid/LoginCornerDecorations";

const showRegisterLink =
  process.env.NEXT_PUBLIC_ENABLE_PUBLIC_REGISTRATION_AND_PASSWORD_RESET !== "false";

export default function Page() {
  const [state, dispatch] = useActionState(login, undefined);

  return (
    <div className="orid-forest-page relative flex min-h-screen w-full items-center justify-center px-4 py-10 sm:py-12">
      {/* Soft ambient glow */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
        <div className="absolute -left-24 -top-24 h-72 w-72 rounded-full bg-amber-200/20 blur-3xl" />
        <div className="absolute -right-20 top-16 h-64 w-64 rounded-full bg-orange-200/15 blur-3xl" />
        <div className="absolute bottom-0 left-1/2 h-48 w-96 -translate-x-1/2 rounded-full bg-amber-300/10 blur-3xl" />
      </div>

      {/* Corner illustrations */}
      <LoginCornerDecorations />

      {/* Centered login card */}
      <div className="relative z-10 w-full max-w-md">
          <div className="mb-5 flex flex-col items-center gap-3 text-center">
            <div className="flex flex-col items-center gap-2.5 sm:flex-row sm:gap-3">
              <DilabLogo height={36} />
              <h1 className="text-2xl font-bold text-amber-950 sm:text-3xl">
                AI–ORID 反思寫作
              </h1>
            </div>
          </div>

        <form action={dispatch} className="kid-shell p-5 sm:p-7">
          <h2 className="mb-1 text-center text-lg font-bold text-amber-950 sm:text-xl">
            歡迎回來！
          </h2>
          <p className="mb-5 text-center text-sm text-amber-800/60 sm:text-base">
            輸入你的帳號密碼登入系統
          </p>

          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="username" className="text-sm font-semibold text-amber-900 sm:text-base">
                帳號
              </Label>
              <Input
                id="username"
                name="username"
                type="text"
                autoComplete="username"
                required
                className="h-11 rounded-xl border-amber-200 bg-amber-50/50 text-base text-amber-950 placeholder:text-amber-400 focus-visible:border-amber-500 focus-visible:ring-2 focus-visible:ring-amber-400/30"
              />
              <FieldError state={state} field="username" />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="password" className="text-sm font-semibold text-amber-900 sm:text-base">
                密碼
              </Label>
              <Input
                id="password"
                name="password"
                type="password"
                required
                className="h-11 rounded-xl border-amber-200 bg-amber-50/50 text-base text-amber-950 placeholder:text-amber-400 focus-visible:border-amber-500 focus-visible:ring-2 focus-visible:ring-amber-400/30"
              />
              <FieldError state={state} field="password" />
            </div>

            <div className="pt-1">
              <SubmitButton text="登入" className="kid-btn-primary w-full" />
            </div>

            <FormError state={state} />
          </div>
        </form>

        {showRegisterLink && (
          <p className="mt-3 text-center text-sm text-amber-800/60 sm:text-base">
            還沒有帳號？{" "}
            <Link
              href="/register"
              className="font-semibold text-amber-700 underline-offset-2 hover:text-amber-900 hover:underline"
            >
              前往註冊
            </Link>
          </p>
        )}
      </div>
    </div>
  );
}
