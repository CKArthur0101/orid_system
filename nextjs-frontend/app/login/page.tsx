"use client";

import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { login } from "@/components/actions/login-action";
import { useActionState } from "react";
import { SubmitButton } from "@/components/ui/submitButton";
import { FieldError, FormError } from "@/components/ui/FormError";

export default function Page() {
  const [state, dispatch] = useActionState(login, undefined);

  return (
    <div className="relative min-h-screen w-full overflow-hidden bg-slate-950 px-4">
      {/* 背景：深藍漸層 + 霧化光暈 */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 bg-[radial-gradient(1000px_600px_at_50%_-10%,rgba(56,189,248,0.18),transparent_60%),radial-gradient(900px_520px_at_10%_30%,rgba(99,102,241,0.14),transparent_60%),radial-gradient(900px_520px_at_90%_70%,rgba(236,72,153,0.10),transparent_60%)]" />
        <div className="absolute inset-0 opacity-60 [background-image:radial-gradient(rgba(255,255,255,0.06)_1px,transparent_1px)] [background-size:18px_18px]" />
      </div>

      {/* 四角裝飾（閱讀/對話/SEL 風格） */}
      <ReadingDecor />

      {/* 置中登入卡 */}
      <div className="relative flex min-h-screen w-full items-center justify-center">
        <form action={dispatch} className="w-full max-w-sm">
          <Card className="rounded-2xl border border-white/10 bg-white/10 shadow-[0_20px_80px_rgba(0,0,0,0.35)] backdrop-blur-xl">
            <CardHeader className="text-center pb-4">
              {/* 發光標題 */}
              <div className="mx-auto mb-2 inline-flex items-center justify-center rounded-2xl px-3 py-2">
                <div className="text-2xl font-semibold tracking-tight text-white drop-shadow-[0_0_18px_rgba(56,189,248,0.35)]">
                  AI–ORID 反思對話系統
                </div>
              </div>

              <CardTitle className="text-xl font-semibold text-white">
                系統登入
              </CardTitle>

              <CardDescription className="text-sm text-white/70">
                請輸入你的電子郵件與密碼登入。
              </CardDescription>
            </CardHeader>

            <CardContent className="grid gap-5 p-6 pt-2">
              <div className="grid gap-2">
                <Label htmlFor="username" className="text-white/80">
                  電子郵件
                </Label>
                <Input
                  id="username"
                  name="username"
                  type="email"
                  placeholder="例如：student@example.com"
                  required
                  className="h-11 rounded-xl border-white/10 bg-white/10 text-white placeholder:text-white/40 focus-visible:ring-2 focus-visible:ring-sky-400/60"
                />
                <FieldError state={state} field="username" />
              </div>

              <div className="grid gap-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="password" className="text-white/80">
                    密碼
                  </Label>
                  <Link
                    href="/password-recovery"
                    className="text-xs text-sky-300 hover:text-sky-200"
                  >
                    忘記密碼？
                  </Link>
                </div>

                <Input
                  id="password"
                  name="password"
                  type="password"
                  required
                  className="h-11 rounded-xl border-white/10 bg-white/10 text-white placeholder:text-white/40 focus-visible:ring-2 focus-visible:ring-sky-400/60"
                />
                <FieldError state={state} field="password" />
              </div>

              {/* 讓你原本的 SubmitButton 保持可用 */}
              <div className="[&>button]:h-11 [&>button]:w-full [&>button]:rounded-xl [&>button]:bg-sky-500 [&>button]:text-white [&>button:hover]:bg-sky-400 [&>button]:shadow-[0_12px_30px_rgba(56,189,248,0.25)]">
                <SubmitButton text="登入" />
              </div>

              <FormError state={state} />

              <div className="mt-1 text-center text-sm text-white/70">
                還沒有帳號嗎？{" "}
                <Link href="/register" className="text-sky-300 hover:text-sky-200">
                  註冊
                </Link>
              </div>

              <div className="text-center text-[11px] text-white/45">
                提示：本系統將引導你依 ORID（客觀→感受→意義→行動）完成反思。
              </div>
            </CardContent>
          </Card>
        </form>
      </div>
    </div>
  );
}

function ReadingDecor() {
  return (
    <div className="pointer-events-none absolute inset-0">
      {/* 左上：對話 */}
      <div className="absolute left-8 top-6 opacity-80">
        <div className="text-6xl drop-shadow-[0_0_18px_rgba(56,189,248,0.28)]">
          💬
        </div>
      </div>

      {/* 左中：繪本 */}
      <div className="absolute left-10 top-40 opacity-85">
        <div className="text-6xl drop-shadow-[0_0_18px_rgba(251,191,36,0.18)]">
          📖
        </div>
      </div>

      {/* 左下：寫作 */}
      <div className="absolute bottom-10 left-10 opacity-85">
        <div className="text-6xl drop-shadow-[0_0_18px_rgba(236,72,153,0.16)]">
          ✏️
        </div>
      </div>

      {/* 右上：靈感 */}
      <div className="absolute right-10 top-8 opacity-80">
        <div className="text-6xl drop-shadow-[0_0_18px_rgba(34,197,94,0.16)]">
          ✨
        </div>
      </div>

      {/* 右中：同理/情緒 */}
      <div className="absolute right-12 top-44 opacity-85">
        <div className="text-6xl drop-shadow-[0_0_18px_rgba(244,63,94,0.16)]">
          🫶
        </div>
      </div>

      {/* 右下：思考 */}
      <div className="absolute bottom-10 right-10 opacity-85">
        <div className="text-6xl drop-shadow-[0_0_18px_rgba(249,115,22,0.14)]">
          🧠
        </div>
      </div>
    </div>
  );
}
