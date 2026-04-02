"use client";

import Link from "next/link";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { login } from "@/components/actions/login-action";
import { useActionState } from "react";
import { SubmitButton } from "@/components/ui/submitButton";
import { FieldError, FormError } from "@/components/ui/FormError";

export default function Page() {
  const [state, dispatch] = useActionState(login, undefined);

  return (
    <div className="relative flex min-h-screen w-full flex-col items-center justify-center overflow-hidden bg-gradient-to-br from-sky-50 via-white to-amber-50/30 px-4">
      {/* Floating decorations */}
      <FloatingDecor />

      {/* Login card */}
      <div className="relative z-10 w-full max-w-lg">
        {/* Logo area */}
        <div className="mb-7 text-center">
          <div className="mx-auto mb-4 flex h-24 w-24 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-400 to-blue-600 shadow-lg shadow-sky-200">
            <span className="text-5xl">📖</span>
          </div>
          <h1 className="text-3xl font-bold text-slate-800">AI–ORID 反思對話</h1>
          <p className="mt-1.5 text-base text-slate-500">閱讀、思考、對話、寫作</p>
        </div>

        <form
          action={dispatch}
          className="rounded-2xl border border-slate-200 bg-white p-8 shadow-xl shadow-slate-200/50 sm:p-10"
        >
          <h2 className="mb-1 text-center text-xl font-bold text-slate-700">
            歡迎回來！
          </h2>
          <p className="mb-7 text-center text-base text-slate-500">
            輸入你的帳號密碼登入系統
          </p>

          <div className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="username" className="text-base font-medium text-slate-600">
                電子郵件
              </Label>
              <Input
                id="username"
                name="username"
                type="email"
                placeholder="例如：student@example.com"
                required
                className="h-12 rounded-xl border-slate-200 bg-slate-50 text-base text-slate-800 placeholder:text-slate-400 focus-visible:ring-2 focus-visible:ring-sky-400/50 focus-visible:border-sky-400"
              />
              <FieldError state={state} field="username" />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="password" className="text-base font-medium text-slate-600">
                  密碼
                </Label>
                <Link
                  href="/password-recovery"
                  className="text-sm text-sky-500 hover:text-sky-600"
                >
                  忘記密碼？
                </Link>
              </div>
              <Input
                id="password"
                name="password"
                type="password"
                required
                className="h-12 rounded-xl border-slate-200 bg-slate-50 text-base text-slate-800 placeholder:text-slate-400 focus-visible:ring-2 focus-visible:ring-sky-400/50 focus-visible:border-sky-400"
              />
              <FieldError state={state} field="password" />
            </div>

            <div className="pt-1 [&>button]:h-12 [&>button]:w-full [&>button]:rounded-xl [&>button]:bg-gradient-to-r [&>button]:from-sky-500 [&>button]:to-blue-600 [&>button]:text-white [&>button]:text-base [&>button]:font-semibold [&>button]:shadow-md [&>button]:shadow-sky-200 [&>button:hover]:from-sky-400 [&>button:hover]:to-blue-500 [&>button]:transition-all">
              <SubmitButton text="登入" />
            </div>

            <FormError state={state} />

            <div className="text-center text-base text-slate-500">
              還沒有帳號嗎？{" "}
              <Link href="/register" className="font-medium text-sky-500 hover:text-sky-600">
                註冊
              </Link>
            </div>
          </div>
        </form>

        {/* ORID steps hint */}
        <div className="mt-7 flex items-center justify-center gap-4 text-slate-400">
          {[
            { icon: "📖", label: "閱讀" },
            { icon: "💬", label: "對話" },
            { icon: "✍️", label: "寫作" },
            { icon: "💡", label: "反思" },
          ].map(({ icon, label }, i) => (
            <div key={label} className="flex items-center gap-1.5">
              {i > 0 && <span className="mr-2 text-slate-300">→</span>}
              <span className="text-xl">{icon}</span>
              <span className="text-sm">{label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function FloatingDecor() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      {/* Top-left blob */}
      <div className="absolute -left-20 -top-20 h-64 w-64 rounded-full bg-sky-200/40 blur-3xl" />
      {/* Top-right blob */}
      <div className="absolute -right-16 -top-16 h-56 w-56 rounded-full bg-amber-200/30 blur-3xl" />
      {/* Bottom-left blob */}
      <div className="absolute -bottom-16 -left-16 h-48 w-48 rounded-full bg-emerald-200/25 blur-3xl" />
      {/* Bottom-right blob */}
      <div className="absolute -bottom-20 -right-20 h-60 w-60 rounded-full bg-violet-200/25 blur-3xl" />

      {/* Scattered emojis */}
      <div className="absolute left-[8%] top-[15%] text-4xl opacity-20 sm:text-5xl">📖</div>
      <div className="absolute right-[10%] top-[12%] text-4xl opacity-15 sm:text-5xl">✨</div>
      <div className="absolute left-[5%] bottom-[18%] text-4xl opacity-15 sm:text-5xl">✏️</div>
      <div className="absolute right-[8%] bottom-[15%] text-4xl opacity-15 sm:text-5xl">💬</div>
      <div className="absolute left-[45%] top-[8%] text-3xl opacity-10 sm:text-4xl">🌟</div>
      <div className="absolute right-[35%] bottom-[10%] text-3xl opacity-10 sm:text-4xl">🦋</div>
    </div>
  );
}
